# Healthcare Data Model

## Entity Relationship Overview

```
HCO (Healthcare Organization)
 └── HCP (Healthcare Provider) [many HCPs per HCO]
      ├── Interactions (many interactions per HCP)
      ├── Rx Aggregates (many product-period records per HCP)
      ├── Patient Support Cases (aggregated to HCP+product+month)
      └── Territory Assignment (one active assignment per HCP)

Trial Sites (linked to HCO, with PI HCP)
```

## Key Tables

### gold_hcp_360

| Column | Type | Description |
|--------|------|-------------|
| hcp_id | VARCHAR | Unique HCP identifier (MDM golden key) |
| npi | VARCHAR | National Provider Identifier (10-digit) |
| full_name | VARCHAR | Standardized full name |
| specialty_code | VARCHAR | Specialty code (ONCO, CARDIO, etc.) |
| specialty_name | VARCHAR | Human-readable specialty name |
| specialty_tier | VARCHAR | Commercial tier (A/B/C/D) |
| state | VARCHAR | Practice state (2-char) |
| territory_id | VARCHAR | Assigned territory |
| is_kol | BOOLEAN | Key Opinion Leader flag |
| is_investigator | BOOLEAN | Clinical investigator flag |
| total_interactions_12m | INTEGER | Interaction count last 12 months |
| interactions_90d | INTEGER | Interaction count last 90 days |
| last_interaction_date | DATE | Most recent interaction date |
| total_rx_12m | INTEGER | Total prescriptions last 12 months |
| avg_market_share | DOUBLE | Average market share across products |
| total_psp_cases | INTEGER | Total patient support cases |
| engagement_score | INTEGER | Composite engagement score (0–100) |
| dq_npi_valid | INTEGER | 1=valid NPI, 0=invalid |
| dq_name_complete | INTEGER | 1=name present, 0=missing |
| gold_created_ts | TIMESTAMP | Gold record creation timestamp |

### gold_hcp_targeting_score

| Column | Type | Description |
|--------|------|-------------|
| hcp_id | VARCHAR | HCP identifier |
| specialty_tier | VARCHAR | Specialty tier |
| territory_id | VARCHAR | Territory |
| state | VARCHAR | State |
| total_interactions_12m | INTEGER | Interaction count (12m) |
| interactions_90d | INTEGER | Interaction count (90d) |
| days_since_last_interaction | INTEGER | Days since last contact |
| positive_outcomes | INTEGER | Count of positive interactions |
| total_rx_12m | INTEGER | Total Rx volume |
| total_new_starts_12m | INTEGER | New patient starts |
| market_share_pct | DOUBLE | Market share % |
| total_psp_cases | INTEGER | PSP case count |
| engagement_score | INTEGER | Engagement score (0–100) |
| is_kol_flag | INTEGER | KOL binary flag |
| is_investigator_flag | INTEGER | Investigator binary flag |
| years_in_practice | INTEGER | Years since graduation |
| targeting_priority | VARCHAR | Rule-based label: A/B/C/D |
| feature_ts | TIMESTAMP | Feature computation timestamp |

### gold_trial_site_priority

| Column | Type | Description |
|--------|------|-------------|
| site_id | VARCHAR | Trial site identifier |
| hco_id | VARCHAR | Linked HCO |
| hco_name | VARCHAR | Organization name |
| state | VARCHAR | Site state |
| trial_id | VARCHAR | Trial identifier |
| enrolled_patients | INTEGER | Total enrolled |
| screen_failures | INTEGER | Failed screenings |
| query_rate | DOUBLE | Data query rate |
| protocol_deviations | INTEGER | Protocol deviation count |
| site_rating | VARCHAR | Excellent/Good/Acceptable/Poor |
| is_active | BOOLEAN | Site currently active |
| enrollment_success_pct | DOUBLE | Enrollment rate % |
| site_quality_score | INTEGER | Composite quality score (0–100) |
| priority_tier | VARCHAR | HIGH/MEDIUM/LOW |
