# Finance Data Strategy: Point-in-Time Feature Quality and Auditability

## The Core Problem This Strategy Solves

The most common cause of fraud model failure is not a modeling problem — it is a **data problem**. Specifically, it is the problem of **temporal data contamination**, also known as data leakage.

When a feature is computed using data that would not have been available at the time of the event being predicted, the model learns relationships that cannot exist at inference time. The model appears to perform well in backtesting but degrades immediately upon production deployment.

This strategy enforces **point-in-time correctness** at the data layer, not the model layer.

---

## Source System Strategy

| Source | Data | Timing | Key Challenge |
|--------|------|--------|--------------|
| Transaction System | All transactions | Near real-time (batch daily) | Volume: 100K+ daily |
| Customer Master | Customer profiles | Weekly refresh | SCD handling required |
| Account System | Account status, limits | Daily | Account state changes |
| Merchant DB | Merchant category, risk | Monthly | Static reference data |
| Device/Login Events | Login patterns | Real-time (batch daily) | Latency sensitive |
| Chargeback System | Fraud labels | 7-60 day lag | Labels arrive after event |
| Bureau Attributes | Credit bureau data | Monthly pull | 30-45 day delay typical |

### Chargeback Label Timing

This is the most critical source timing issue. Fraud chargebacks arrive **after** the transaction, with a lag of 7 to 60 days. This means:

1. **Label availability**: When training a model on historical data, we only use chargebacks received within the training window
2. **No look-ahead**: A transaction on Day 1 is labeled based on chargebacks received by Day 60 — future chargebacks are excluded from training labels
3. **Label noise**: Some fraud transactions never generate chargebacks; the `is_fraud` column uses all available ground truth at analysis time

---

## Data Quality Strategy

### Feature Freshness Tiers

| Feature | Max Staleness | Action if Stale |
|---------|--------------|----------------|
| Transaction amount | 0 hours (real-time) | Block scoring |
| Transaction timestamp | 0 hours | Block scoring |
| Customer 30-day history | 24 hours | Warn, continue |
| Bureau score | 45 days | Flag score with caveat |
| Device events | 4 hours | Warn, degrade confidence |

### Point-in-Time Correctness Enforcement

Every aggregated feature must be computed as-of the event timestamp:

```sql
-- The temporal join pattern enforces PIT correctness
JOIN transactions h
  ON h.customer_id = t.customer_id
  AND h.transaction_date BETWEEN t.transaction_date - INTERVAL '30 days'
                              AND t.transaction_date  -- critical upper bound
  AND h.transaction_id != t.transaction_id          -- exclude current event
```

This pattern is used for ALL historical aggregations:
- `customer_tx_count_30d`
- `customer_avg_amount_30d`
- `customer_total_amount_30d`
- `days_since_last_tx`
- `prior_fraud_count`

---

## Data Governance Strategy

### Regulatory Requirements

| Regulation | Requirement | How Addressed |
|-----------|-------------|--------------|
| **Basel III** | Model risk governance | Model card, version control, evaluation report |
| **GDPR Article 22** | Right to explanation | Per-transaction top feature explanations |
| **SR 11-7** | Model validation | Cross-validation, OOT evaluation |
| **PCI DSS** | Cardholder data protection | No real card numbers; anonymized IDs |

### Access Control

| Data Asset | Who Can Read | Who Can Write |
|-----------|-------------|--------------|
| bronze_transactions | Data Engineering | ETL Pipeline only |
| silver_transactions_clean | Data Engineering, Analytics | Pipeline only |
| gold_transaction_risk_features | ML Team, Compliance | Pipeline only |
| gold_fraud_risk_scores | Fraud Operations, Compliance | ML Pipeline only |
| Audit trail | Compliance, Legal, Regulators | Read-only archive |

---

## Feature Quality Strategy

### Feature Quality Dimensions

1. **Completeness**: What fraction of records have non-null values?
2. **Freshness**: Is the feature computed from data within its defined temporal window?
3. **Validity**: Is the feature value within an expected business range?
4. **Consistency**: Do training and inference features use the same computation logic?

### Feature Quality Scoring

Each feature has a quality score computed daily:

```
feature_quality_score = completeness_pct × freshness_score × validity_score
```

If any feature's quality score drops below threshold, the model's predictions for affected records are flagged with reduced confidence.

---

## Semantic / Feature Layer Strategy

The feature layer (`gold_transaction_risk_features`) is designed with the following principles:

1. **Self-contained**: Every feature needed for scoring is in one table
2. **Timestamped**: `feature_ts` records when features were computed
3. **Labeled**: `is_fraud` ground truth included for training use; not used at inference
4. **Explainable**: Feature names are descriptive and match business language
5. **No leakage**: Enforced via temporal join patterns

---

## AI Consumption Strategy

### Training vs Inference

| Concern | How Addressed |
|---------|-------------|
| Data leakage prevention | Temporal join pattern in `gold_transaction_risk_features` |
| Class imbalance (~3% fraud) | SMOTE oversampling + class_weight='balanced' |
| Feature consistency | Same SQL logic used at training and inference |
| Model explainability | SHAP values + feature importance per prediction |
| Auditability | Every prediction links to transaction_id + batch_id |

### Model Card

- **Model name**: Fraud Detection Classifier v1.0
- **Algorithm**: Random Forest (300 trees, balanced class weights)
- **Training data**: `gold_transaction_risk_features`
- **Target**: `is_fraud` (binary, 3% positive rate)
- **Evaluation**: AUC-ROC, AUC-PR, Precision, Recall at 0.5 threshold
- **Key limitation**: Trained on synthetic data only
- **Temporal correctness**: All features are point-in-time correct

---

## Observability Strategy

| Signal | Tool | Alert Threshold |
|--------|------|----------------|
| Feature freshness | Daily pipeline check | Feature > 24h old |
| Fraud rate drift | Distribution comparison | Rate changes > 1% in 7d |
| AUC degradation | Weekly model evaluation | AUC drops > 0.03 |
| Feature null rates | Data quality report | Completeness < 95% |
| Transaction volume anomaly | Pipeline row count check | < 80% of rolling 7-day avg |
