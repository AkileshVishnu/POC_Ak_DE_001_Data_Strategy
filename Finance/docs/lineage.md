# Finance Data Lineage

## Source to Bronze Mapping

| Source File | Bronze Table | Key Columns | Metadata Added |
|-------------|-------------|------------|---------------|
| transactions.csv | bronze_transactions | transaction_id, customer_id, amount, is_fraud | _batch_id, _load_ts |
| customers.csv | bronze_customers | customer_id, age, state, income_band | _batch_id, _load_ts |
| accounts.csv | bronze_accounts | account_id, customer_id, account_type | _batch_id, _load_ts |
| merchants.csv | bronze_merchants | merchant_id, category, risk_flag | _batch_id, _load_ts |
| chargebacks.csv | bronze_chargebacks | chargeback_id, transaction_id, reason_code | _batch_id, _load_ts |
| device_events.csv | bronze_device_events | event_id, customer_id, is_new_device | _batch_id, _load_ts |
| bureau_attributes.csv | bronze_bureau_attrs | customer_id, bureau_score, credit_utilization | _batch_id, _load_ts |

## Bronze to Silver Transformations

| Bronze | Silver | Transformations | Exclusions |
|--------|--------|----------------|-----------|
| bronze_transactions | silver_transactions_clean | Amount → DOUBLE; date cast; quality flags | amount ≤ 0; future dates |
| bronze_customers | silver_customers_clean | Name UPPER; age cast; QUALIFY dedup | Null customer_id |
| bronze_merchants | silver_merchants_clean | Name trim; state UPPER | Null merchant_id |
| bronze_device_events | silver_device_events_clean | Date cast; boolean casts | Null customer_id |

## Silver to Gold Transformations

### Critical: Point-in-Time Feature Engineering

The transformation from Silver to `gold_transaction_risk_features` is the most critical step. It uses a **temporal self-join** to ensure all historical features use only data before each transaction's timestamp:

```
silver_transactions_clean (current transaction T)
  + silver_transactions_clean (historical H, where H.date < T.date)  ← PIT constraint
  + silver_device_events_clean (events, where event_date <= T.date)  ← PIT constraint
  + gold_customer_360 (bureau data, computed once from bronze_bureau_attrs)
  + silver_merchants_clean (static reference data)
  ↓
gold_transaction_risk_features (one row per transaction, all features as-of T)
```

| Silver Table(s) | Gold Table | Transformation |
|----------------|-----------|---------------|
| silver_customers_clean + bronze_bureau_attrs | gold_customer_360 | JOIN; compute tenure_days |
| Multiple silver tables | gold_transaction_risk_features | PIT temporal join; rolling aggregations |
| gold_transaction_risk_features | gold_customer_risk_profile | Customer-level aggregation; risk tier assignment |

## Gold to ML/Dashboard Consumption

| Gold Table | Consumer | Usage |
|-----------|---------|-------|
| gold_transaction_risk_features | train_model.py | All FEATURE_COLS + is_fraud label |
| gold_transaction_risk_features | streamlit_app.py | Fraud monitoring page |
| gold_customer_risk_profile | streamlit_app.py | Customer risk profile page |
| gold_customer_360 | streamlit_app.py | Customer profile view |

## Example Lineage: Fraud Score for TX_00012345

```
Fraud probability: 0.87 (HIGH RISK)

Feature: amount_vs_avg_ratio = 8.4
  gold_transaction_risk_features.amount_vs_avg_ratio
  = amount / customer_avg_amount_30d
  = $1,240 / $147.62
  
  amount ($1,240):
  ← silver_transactions_clean.amount (TX_00012345)
  ← bronze_transactions (batch_id: 20240601_120000)
  ← transactions.csv (source: Transaction System)
  
  customer_avg_amount_30d ($147.62):
  ← AVG(silver_transactions_clean.amount)
    WHERE customer_id = CUST_001234
    AND transaction_date BETWEEN 2024-05-01 AND 2024-06-01  ← PIT window
    AND transaction_id != TX_00012345  ← exclude self

Feature: is_late_night = 1 (transaction_hour = 2)
  ← silver_transactions_clean.transaction_hour
  ← bronze_transactions (same batch)

Feature: new_device_events_7d = 2
  ← COUNT of silver_device_events_clean
    WHERE customer_id = CUST_001234
    AND event_date BETWEEN 2024-05-25 AND 2024-06-01  ← PIT window
    AND event_type = 'New Device'

Model decision:
  RandomForestClassifier v1.0 (trained: 2024-07-01)
  Top drivers: amount_vs_avg_ratio (0.24), is_late_night (0.18), prior_fraud_count (0.15)
```
