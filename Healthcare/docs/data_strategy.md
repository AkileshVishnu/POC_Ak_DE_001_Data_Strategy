# Healthcare Data Strategy: MDM-First Governed Data Product

## Overview

The Healthcare POC implements an **MDM-First Governed Data Product** strategy. This is the appropriate strategy when:
- The same real-world entity (HCP, HCO) exists in multiple source systems
- Entity identity must be resolved before AI can consume the data
- Privacy regulations impose strict controls on patient-level data
- AI outputs (targeting scores, recommendations) must be auditable and explainable

---

## Source System Strategy

### Source Systems in Scope

| Source | Data | Identity Key | Quality Profile |
|--------|------|-------------|----------------|
| CRM | HCP profiles, interactions | CRM-internal ID | High quality names, inconsistent NPIs |
| Prescription Feed | Rx aggregates by HCP | Partial NPI, DEA | Accurate volumes, delayed by 45 days |
| Speaker Bureau | HCP speaker history | Name + email | Variable name formatting, incomplete NPIs |
| EHR Integration | Clinical affiliations | NPI | High NPI accuracy, limited profile data |
| Territory System | Rep-territory-HCP mapping | CRM ID | Authoritative for territory assignments |

### Source Disambiguation

Each source is assigned a namespace prefix to prevent ID collisions across systems. This is the foundation of the MDM approach: before resolving to a golden record, all records must be clearly identified as originating from a specific source.

### Data Latency Profile

| Source | Latency | Batch Schedule | Impact on AI |
|--------|---------|----------------|-------------|
| CRM Interactions | Same day | Daily | Targeting scores may lag 1 day |
| Rx Feed | 45-day delay | Monthly | Rx-based features are 45d stale |
| EHR Integration | Weekly | Weekly | Affiliation data may lag 7 days |

---

## MDM Data Ownership

| Dataset | Business Owner | Technical Steward | Governance Board |
|---------|---------------|------------------|-----------------|
| HCP Master Golden Record | Commercial Ops | MDM Platform Team | Data Governance Council |
| HCO Master | Commercial Ops | MDM Platform Team | Data Governance Council |
| Interaction Data | CRM Admin | Data Engineering | CRM Operations |
| Prescription Data | Market Analytics | Market Data Team | Analytics Governance |
| Patient Support (aggregated) | Patient Services | Analytics + Privacy Officer | Privacy Review Board |

---

## Data Quality Strategy

### Quality Dimensions and Thresholds

| Dimension | Metric | Target | Action if Missed |
|-----------|--------|--------|-----------------|
| **Completeness** | NPI present in HCP records | ≥ 95% | Flag records, exclude from AI scoring |
| **Uniqueness** | No duplicate hcp_id in Gold | 100% | Block pipeline, alert MDM team |
| **Validity** | NPI matches 10-digit format | ≥ 95% | Flag as unverified, reduce confidence score |
| **Consistency** | Specialty code in approved list | ≥ 99% | Remap or flag for review |
| **Timeliness** | Interaction data loaded within 24h | ≥ 98% | Alert data engineering |
| **Referential Integrity** | Interactions linked to known HCPs | ≥ 95% | Quarantine orphaned records |

### Privacy-Preserving Data Quality

Patient support data requires an additional quality dimension: **privacy compliance**.
- Individual patient records are **never** stored in the Gold or Silver layers
- Patient support data is aggregated to HCP + product + month level at the Bronze → Silver transition
- Minimum cohort size (n ≥ 10) is enforced before any aggregate is exposed

---

## Data Governance Strategy

### Access Tiers

| Data Asset | Tier | Who Can Access |
|-----------|------|---------------|
| Bronze raw files | RESTRICTED | Data Engineering only |
| Silver HCP/HCO data | INTERNAL | Analytics, Commercial Ops, Medical Affairs |
| Gold HCP 360 | INTERNAL | Commercial, Analytics, Medical Affairs |
| Gold targeting scores | CONTROLLED | Commercial Ops (read), AI team (read) |
| Patient support aggregates | CONTROLLED | Patient Services, Analytics (aggregate only) |
| Trial site data | RESTRICTED | Medical Affairs, Clinical Ops only |

### Data Retention

| Layer | Retention | Reason |
|-------|-----------|--------|
| Bronze raw | 7 years | Regulatory audit requirement |
| Silver | 5 years | Operational requirement |
| Gold | 3 years | Business requirement |
| Model artifacts | Indefinite | Auditability requirement |

---

## Metadata and Lineage Strategy

Every table in every layer carries mandatory metadata columns:
- `_batch_id`: Unique identifier for the ingestion batch
- `_load_ts`: Timestamp when the record was loaded
- `_source_file`: Source file or API endpoint
- `_source_system`: Originating source system

At the Gold layer, lineage is extended:
- `gold_created_ts`: Timestamp when the Gold record was computed
- Every Gold field is traceable to a specific Silver field and Silver table

---

## Data Product Strategy

### Gold Layer Data Products

| Data Product | Consumers | SLA | Refresh |
|-------------|----------|-----|---------|
| `gold_hcp_360` | All commercial analytics | 99.5% availability | Daily |
| `gold_hcp_targeting_score` | AI targeting model | Data freshness ≤ 24h | Daily |
| `gold_patient_support_summary` | Patient Services dashboard | 99% availability | Monthly |
| `gold_trial_site_priority` | Medical Affairs | 99% availability | Quarterly |

### Data Product Contract

Each data product publishes:
1. Schema with field-level definitions
2. Quality SLAs (freshness, completeness thresholds)
3. Owner and steward contacts
4. Known limitations (e.g., Rx data 45-day lag)

---

## Semantic / Feature Layer Strategy

The feature layer (`gold_hcp_targeting_score`) bridges data products and the AI model by:

1. **Computing engagement score**: Composite signal from interaction frequency, outcome quality, specialty tier, and KOL status
2. **Deriving targeting priority**: Rule-based label that combines Rx volume, engagement, and specialty — serves as the supervised learning target
3. **Flagging data quality per feature**: `dq_npi_valid` flag passes into the feature set so the model knows when a feature is derived from incomplete data
4. **No leakage**: All features use only data available as of the feature computation date

---

## AI Consumption Strategy

### Model Input Requirements

| Feature | Source | Recency Required | Sensitivity |
|---------|--------|-----------------|------------|
| engagement_score | gold_hcp_360 | ≤ 24 hours | None |
| total_rx_12m | silver_rx_aggregates | ≤ 45 days | None |
| specialty_tier | silver_hcp_standardized | ≤ 7 days | None |
| is_kol | silver_hcp_standardized | ≤ 7 days | None |
| total_psp_cases | silver_patient_support_agg | ≤ 30 days | Aggregated — no PHI |

### Explainability Requirements

Every HCP targeting score must be explainable. The model produces:
- Targeting priority (A/B/C/D)
- Top 3 features driving the score
- Confidence score
- Feature freshness timestamp

This allows field reps to understand *why* an HCP is prioritized and allows compliance teams to audit the AI recommendation.

---

## Observability Strategy

### Pipeline Health Monitoring

| Signal | Threshold | Alert Condition |
|--------|-----------|----------------|
| Bronze row count vs previous batch | ≥ 90% of previous | Sudden drop suggests feed issue |
| Silver quality score | ≥ 85% | Quality degradation |
| Gold uniqueness | 100% | Deduplication failure |
| Model feature freshness | ≤ 24h | Feature data staleness |
| HCP count in Gold vs Bronze | ≤ 5% delta | MDM merge issue |

### Data Drift Monitoring

After model deployment, the following distributions are monitored for drift:
- `engagement_score` distribution by specialty tier
- `targeting_priority` tier distribution
- `total_rx_12m` percentile distribution

A drift alert triggers model retraining review if distributions shift by > 10% in 30 days.
