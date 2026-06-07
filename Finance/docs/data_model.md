# Finance Data Model

## Entity Relationship

```
Customer (1)
  ├── Account (many per customer)
  ├── Transaction (many per customer)
  │    ├── Merchant (1 per transaction)
  │    └── Chargeback (0 or 1 per fraud transaction, with lag)
  ├── Device Event (many per customer)
  └── Bureau Attributes (1 per customer, monthly pull)
```

## Key Tables

### gold_transaction_risk_features (Primary ML Input)

| Column | Type | PIT? | Description |
|--------|------|------|-------------|
| transaction_id | VARCHAR | N/A | Unique transaction ID |
| customer_id | VARCHAR | N/A | Customer reference |
| transaction_date | DATE | N/A | Event timestamp |
| amount | DOUBLE | N/A | Transaction amount |
| transaction_hour | INTEGER | N/A | Hour of day (0-23) |
| is_online | BOOLEAN | N/A | Online transaction flag |
| is_international | BOOLEAN | N/A | International flag |
| customer_tx_count_30d | INTEGER | ✓ | Tx count in 30d BEFORE this tx |
| customer_avg_amount_30d | DOUBLE | ✓ | Avg amount in 30d BEFORE this tx |
| customer_max_amount_30d | DOUBLE | ✓ | Max amount in 30d BEFORE |
| customer_total_amount_30d | DOUBLE | ✓ | Total spend in 30d BEFORE |
| customer_tx_count_7d | INTEGER | ✓ | Tx count in 7d BEFORE |
| days_since_last_tx | INTEGER | ✓ | Days since prior tx (BEFORE) |
| distinct_states_30d | INTEGER | ✓ | Distinct states in 30d BEFORE |
| prior_fraud_count | INTEGER | ✓ | Prior confirmed frauds (BEFORE) |
| amount_vs_avg_ratio | DOUBLE | ✓ | amount / avg_amount_30d (PIT) |
| is_late_night | INTEGER | N/A | Hour in [0,4] flag |
| new_device_events_7d | INTEGER | ✓ | New device events in 7d BEFORE |
| vpn_events_7d | INTEGER | ✓ | VPN logins in 7d BEFORE |
| bureau_score | INTEGER | N/A | Bureau score (monthly) |
| credit_utilization_pct | DOUBLE | N/A | Bureau utilization |
| num_derogatory_marks | INTEGER | N/A | Bureau derogatory count |
| customer_tenure_days | INTEGER | N/A | Days since account opening |
| merchant_risk_flag | BOOLEAN | N/A | Merchant risk indicator |
| is_fraud | BOOLEAN | N/A | Ground truth label (training only) |
| feature_ts | TIMESTAMP | N/A | Feature computation timestamp |

**PIT = Point-in-Time: features marked ✓ are computed using only data before transaction_date**

### gold_customer_risk_profile

| Column | Type | Description |
|--------|------|-------------|
| customer_id | VARCHAR | Customer ID |
| total_transactions | INTEGER | All-time transaction count |
| confirmed_fraud_count | INTEGER | Confirmed fraud transactions |
| fraud_rate_pct | DOUBLE | % of transactions that are fraud |
| avg_transaction_amount | DOUBLE | Average transaction size |
| max_transaction_amount | DOUBLE | Largest transaction |
| max_distinct_states | INTEGER | Max states in any 30d window |
| avg_bureau_score | DOUBLE | Average bureau score |
| risk_tier | VARCHAR | CONFIRMED_FRAUD / HIGH / MEDIUM / LOW |
| gold_created_ts | TIMESTAMP | Record creation time |
