# Finance Data Governance

## Sensitive Data Handling

All data in this POC is **100% synthetic**. No real financial data, PII, or account information is used.

### Classification

| Data Type | Classification | Handling in POC |
|-----------|---------------|----------------|
| Customer name | PII | Synthetic names only |
| Account number | Sensitive Financial | Synthetic IDs |
| Transaction amount | Financial | Synthetic realistic values |
| Card number | PCI-DSS Protected | Not stored — not generated |
| SSN | PII | Not stored — not generated |
| Credit score | Sensitive | Synthetic bureau scores |
| Fraud labels | Sensitive | Synthetic with realistic 3% rate |

## Access Control

In a production system:
- **Fraud labels (is_fraud)** are read-only after labeling pipeline runs
- **Gold feature tables** accessible only by ML pipeline service accounts
- **Audit trail** is append-only and accessible to Compliance and Legal only
- **Raw transaction data** is accessible only to Data Engineering

## Data Masking Approach

| Field | Masking in Analytics | Rationale |
|-------|---------------------|-----------|
| customer_id | Consistent pseudonym | Allows joins; hides real identity |
| transaction_id | Retained | Required for audit trail |
| amount | Retained (no mask) | Required for fraud analysis |
| account_id | Consistent pseudonym | Allows account-level aggregation |
| merchant_id | Retained | Public reference data |

## Auditability

Every fraud score produced by this system is auditable:

1. `fraud_probability` → `transaction_id` → `silver_transactions_clean`
2. `transaction_id` → `_batch_id` → ingestion log (date + source file)
3. Feature values → feature computation SQL (documented in `docs/lineage.md`)
4. Model version → `outputs/model_metadata.json` (training data, algorithm, eval metrics)

**Regulatory audit response time**: Any fraud decision can be explained within minutes by querying the audit trail.

## Compliance Considerations

| Regulation | Relevance | POC Status |
|-----------|-----------|-----------|
| **GDPR Article 22** | Right to explanation of automated decisions | Addressed via per-prediction feature explanations |
| **PCI DSS** | Card data protection | No card data generated or stored |
| **Basel III SR 11-7** | Model risk governance | Model card + evaluation report in outputs/ |
| **FCRA** | Credit reporting accuracy | Bureau attributes are synthetic; disclosure not required |

## Limitations of This POC

- No real encryption at rest or in transit (uses local DuckDB file)
- No production-grade RBAC (local file access only)
- Fraud labels are rule-based synthetic labels, not real chargeback data
- Model is not validated against out-of-time data (OOT validation)
- No model monitoring or drift detection in production
