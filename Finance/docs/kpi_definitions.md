# Finance KPI Definitions

## Fraud Rate

| Field | Value |
|-------|-------|
| **KPI Name** | Transaction Fraud Rate |
| **Business Definition** | Percentage of transactions confirmed as fraudulent within the reporting period |
| **Calculation** | `SUM(is_fraud) / COUNT(*) × 100` |
| **Source Tables** | `gold_transaction_risk_features` |
| **Refresh Frequency** | Daily |
| **Data Quality Dependencies** | Requires timely chargeback labels; labels may lag 7-60 days |
| **Owner** | Fraud Operations |

## Chargeback Rate

| Field | Value |
|-------|-------|
| **KPI Name** | Chargeback Rate |
| **Business Definition** | Number of chargebacks received per 1,000 transactions in a period |
| **Calculation** | `COUNT(chargebacks) / COUNT(transactions) × 1000` |
| **Source Tables** | `bronze_chargebacks`, `silver_transactions_clean` |
| **Refresh Frequency** | Weekly |
| **Data Quality Dependencies** | Chargeback lag of 7-60 days affects recency; report should state cutoff date |
| **Owner** | Fraud Operations |

## Customer Risk Score

| Field | Value |
|-------|-------|
| **KPI Name** | Customer Risk Tier |
| **Business Definition** | Four-tier risk classification (CONFIRMED_FRAUD, HIGH, MEDIUM, LOW) derived from transaction behavior and bureau attributes |
| **Calculation** | Rule-based: CONFIRMED_FRAUD if fraud_count > 0; HIGH if avg_amount_deviation > 5 and distinct states > 3; MEDIUM if credit_utilization > 80% or derogatory_marks > 2; LOW otherwise |
| **Source Tables** | `gold_customer_risk_profile` |
| **Refresh Frequency** | Daily |
| **Data Quality Dependencies** | Requires bureau score (45-day lag); uses prior_fraud_count (point-in-time correct) |
| **Owner** | Risk Management |

## Feature Freshness

| Field | Value |
|-------|-------|
| **KPI Name** | Feature Freshness (hours) |
| **Business Definition** | Number of hours since each feature was last recomputed |
| **Calculation** | `DATEDIFF('hour', feature_ts, CURRENT_TIMESTAMP)` |
| **Source Tables** | `gold_transaction_risk_features` |
| **Refresh Frequency** | Checked hourly in production |
| **Data Quality Dependencies** | Pipeline must run successfully to update feature_ts |
| **Owner** | Data Engineering |

## Model AUC-ROC

| Field | Value |
|-------|-------|
| **KPI Name** | Fraud Model AUC-ROC |
| **Business Definition** | Area under the ROC curve measuring the model's ability to discriminate between fraud and non-fraud transactions |
| **Calculation** | Standard sklearn roc_auc_score on held-out test set |
| **Source Tables** | `gold_transaction_risk_features` (test split) |
| **Refresh Frequency** | Per model retraining |
| **Data Quality Dependencies** | Requires point-in-time correct features; any leakage inflates this metric artificially |
| **Owner** | ML Engineering |
