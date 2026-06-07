# Healthcare KPI Definitions

## HCP Engagement Score

| Field | Value |
|-------|-------|
| **KPI Name** | HCP Engagement Score |
| **Business Definition** | A composite 0–100 score reflecting the depth and quality of recent HCP engagement across interaction activity, prescription behavior, and strategic importance |
| **Calculation** | `MIN(100, MAX(0, (interactions_90d × 8) + (positive_outcomes × 5) + specialty_tier_points + kol_bonus))` where specialty_tier_points: A=20, B=15, C=10, D=5; kol_bonus=15 |
| **Source Tables** | `silver_interactions_clean`, `silver_hcp_standardized` |
| **Refresh Frequency** | Daily |
| **Data Quality Dependencies** | Requires valid interaction_date, valid hcp_id linkage |
| **Owner** | Commercial Analytics |

---

## Targeting Priority

| Field | Value |
|-------|-------|
| **KPI Name** | HCP Targeting Priority Tier |
| **Business Definition** | A four-tier (A/B/C/D) classification of HCPs by commercial prioritization, used to allocate field rep time and resource |
| **Calculation** | Rule-based: A = Tier-A specialty + engagement ≥ 60 + rx ≥ 50; B = Tier A/B + engagement ≥ 40; C = engagement ≥ 20 OR rx ≥ 20; D = all others |
| **Source Tables** | `gold_hcp_360`, `gold_hcp_targeting_score` |
| **Refresh Frequency** | Daily |
| **Data Quality Dependencies** | Requires valid engagement_score, total_rx_12m, specialty_tier |
| **Owner** | Commercial Strategy |

---

## Patient Support Case Volume

| Field | Value |
|-------|-------|
| **KPI Name** | PSP Case Volume (Territory) |
| **Business Definition** | Total number of patient support program cases opened in a territory per quarter, by case type |
| **Calculation** | `SUM(case_count)` grouped by territory_id, product, case_type, quarter |
| **Source Tables** | `silver_patient_support_agg`, `silver_hcp_standardized` |
| **Refresh Frequency** | Monthly |
| **Data Quality Dependencies** | Requires hcp_id linkage to territory; aggregation enforces minimum cohort of 10 |
| **Owner** | Patient Services |

---

## Trial Site Enrollment Performance

| Field | Value |
|-------|-------|
| **KPI Name** | Trial Site Enrollment Success Rate |
| **Business Definition** | Percentage of screened patients who were successfully enrolled at a clinical trial site |
| **Calculation** | `enrolled_patients / NULLIF(enrolled_patients + screen_failures, 0) × 100` |
| **Source Tables** | `silver_trial_sites_clean` |
| **Refresh Frequency** | Quarterly |
| **Data Quality Dependencies** | Requires non-null enrolled_patients and screen_failures |
| **Owner** | Medical Affairs |

---

## Site Quality Score

| Field | Value |
|-------|-------|
| **KPI Name** | Clinical Trial Site Quality Score |
| **Business Definition** | A 0–100 composite score reflecting a trial site's operational performance, enrollment success, and protocol compliance |
| **Calculation** | `enrolled_patients × 2 + site_rating_score - protocol_deviations × 5 - query_rate × 100` clamped to [0, 100] |
| **Source Tables** | `silver_trial_sites_clean`, `silver_hco_standardized` |
| **Refresh Frequency** | Quarterly |
| **Data Quality Dependencies** | Requires site_rating, protocol_deviations, query_rate |
| **Owner** | Clinical Operations |

---

## Territory Coverage Index

| Field | Value |
|-------|-------|
| **KPI Name** | Territory Coverage Index |
| **Business Definition** | Percentage of Priority A and B HCPs in a territory who have had at least one interaction in the last 90 days |
| **Calculation** | `COUNT(HCPs with interactions_90d > 0 AND priority IN (A,B)) / COUNT(all HCPs with priority IN (A,B)) × 100` |
| **Source Tables** | `gold_hcp_targeting_score`, `silver_interactions_clean` |
| **Refresh Frequency** | Weekly |
| **Data Quality Dependencies** | Requires current interaction data (≤ 24h old) and valid targeting priority |
| **Owner** | Commercial Operations |
