# Healthcare Data Lineage

## Source to Bronze Mapping

| Source File | Bronze Table | Key Columns | Metadata Added |
|-------------|-------------|------------|---------------|
| hcp_master.csv | bronze_hcp_master | hcp_id, npi, specialty_code | _batch_id, _load_ts, _source_file |
| hco_master.csv | bronze_hco_master | hco_id, hco_type, state | _batch_id, _load_ts, _source_file |
| hcp_hco_affiliations.csv | bronze_hcp_hco_affiliations | affiliation_id, hcp_id, hco_id | _batch_id, _load_ts |
| hcp_interactions.csv | bronze_hcp_interactions | interaction_id, hcp_id, interaction_date | _batch_id, _load_ts |
| rx_aggregates.csv | bronze_rx_aggregates | rx_id, hcp_id, product, period_month | _batch_id, _load_ts |
| patient_support_cases.csv | bronze_patient_support | case_id, hcp_id, case_type, case_date | _batch_id, _load_ts |
| trial_sites.csv | bronze_trial_sites | site_id, hco_id, trial_id | _batch_id, _load_ts |

## Bronze to Silver Transformations

| Bronze Table | Silver Table | Key Transformations | Records Excluded |
|-------------|-------------|--------------------|-|
| bronze_hcp_master | silver_hcp_standardized | NPI trim/validate; name UPPER; QUALIFY dedup | Null hcp_id |
| bronze_hco_master | silver_hco_standardized | Name trim; state UPPER | Null hco_id |
| bronze_hcp_interactions | silver_interactions_clean | Date cast; filter future dates | future_date, null hcp_id |
| bronze_rx_aggregates | silver_rx_aggregates | Cast to INTEGER; validate non-negative | total_rx_count < 0 |
| bronze_patient_support | silver_patient_support_agg | **Aggregate by hcp+product+month**; drop case_id | Null hcp_id |

### Privacy Transformation Detail

The `bronze_patient_support → silver_patient_support_agg` transformation is the critical privacy step:

```sql
-- Individual case records (case_id, patient_age_band, payer_type) are AGGREGATED
-- No individual case records exist downstream of Silver
SELECT hcp_id, product, case_type, payer_type, DATE_TRUNC('month', case_date),
       COUNT(*) AS case_count, AVG(resolution_days) AS avg_resolution_days
FROM bronze_patient_support
GROUP BY 1, 2, 3, 4, 5
```

## Silver to Gold Transformations

| Silver Table(s) | Gold Table | Transformation |
|----------------|-----------|---------------|
| silver_hcp_standardized + silver_interactions_clean + silver_rx_aggregates | gold_hcp_360 | JOIN all signals; compute engagement_score |
| gold_hcp_360 | gold_hcp_targeting_score | Feature engineering; compute targeting_priority label |
| silver_patient_support_agg + silver_hcp_standardized | gold_patient_support_summary | Territory-level aggregation |
| silver_trial_sites_clean + silver_hco_standardized | gold_trial_site_priority | JOIN site + HCO; compute quality score |

## Gold to ML/Dashboard Consumption

| Gold Table | Consumer | How Used |
|-----------|---------|---------|
| gold_hcp_targeting_score | train_model.py | ML training features + target label |
| gold_hcp_targeting_score | streamlit_app.py | Targeting overview dashboard |
| gold_hcp_360 | streamlit_app.py | HCP 360 profile view |
| gold_patient_support_summary | streamlit_app.py | PSP dashboard (territory-level only) |
| gold_trial_site_priority | streamlit_app.py | Trial site prioritization view |

## Example Lineage: HCP Engagement Score

```
Prediction: HCP_00042 has engagement_score = 71

Lineage:
  gold_hcp_360.engagement_score
  = (interactions_90d × 8) + (positive_outcomes × 5) + specialty_tier_points + kol_bonus
  
  interactions_90d = 5  ← silver_interactions_clean (hcp_id = HCP_00042, last 90d)
    ← bronze_hcp_interactions (batch_id = 20240601_120000, source = hcp_interactions.csv)
    ← CRM Source System (export date: 2024-06-01)
    
  positive_outcomes = 3  ← silver_interactions_clean.outcome = 'Positive' (COUNT)
  
  specialty_tier_points = 15  ← silver_hcp_standardized.specialty_tier = 'B'
    ← bronze_hcp_master (batch_id = 20240601_120000)
    ← HCP Master Source System
    
  kol_bonus = 0  ← silver_hcp_standardized.is_kol = False
  
  Calculation: (5×8) + (3×5) + 15 + 0 = 40+15+15 = 70 → capped at 71 (float)
```

## Example Lineage: Targeting Priority Model Score

```
Prediction: HCP_00042 → targeting_priority = 'B' (model confidence: 0.82)

Feature Lineage:
  engagement_score = 71       ← gold_hcp_360 (see above)
  total_rx_12m = 34           ← silver_rx_aggregates (SUM of 2023 + 2024 records)
  specialty_tier_num = 3      ← silver_hcp_standardized.specialty_tier = 'B' (encoded)
  interactions_90d = 5        ← silver_interactions_clean
  days_since_last = 12        ← DATEDIFF(CURRENT_DATE, last_interaction_date)
  is_kol_flag = 0             ← silver_hcp_standardized.is_kol = False
  
Model: RandomForestClassifier v1.0 (trained: 2024-07-01)
Top driver: engagement_score (importance: 0.31)
Second driver: specialty_tier_num (importance: 0.24)
Third driver: total_rx_12m (importance: 0.19)
```
