# Manufacturing KPI Definitions

## Asset Health Score

| Field | Value |
|-------|-------|
| **KPI Name** | Asset Health Score |
| **Business Definition** | A composite 0–100 score reflecting a piece of equipment's current operational health, combining sensor quality, failure history, and age-adjusted remaining useful life |
| **Calculation** | `avg_sensor_quality × 0.4 + (100 - failure_count_penalty) × 0.3 + (100 - age_utilization_pct) × 0.3` |
| **Source Tables** | `gold_sensor_quality_score`, `silver_failure_events_clean`, `silver_assets_clean` |
| **Refresh Frequency** | Daily |
| **Data Quality Dependencies** | Requires valid sensor quality score; uses failure history from last 12 months |
| **Owner** | Plant Operations |

## Sensor Missingness Rate

| Field | Value |
|-------|-------|
| **KPI Name** | Sensor Missingness Rate |
| **Business Definition** | Percentage of expected sensor readings that were not received in the reporting period |
| **Calculation** | `(expected_reading_count - valid_readings) / expected_reading_count × 100` |
| **Source Tables** | `gold_sensor_quality_score` |
| **Refresh Frequency** | Daily |
| **Data Quality Dependencies** | Requires accurate expected_reading_count based on sensor polling frequency |
| **Owner** | Data Engineering / SCADA Team |

## Anomaly Count

| Field | Value |
|-------|-------|
| **KPI Name** | Sensor Anomaly Count |
| **Business Definition** | Count of sensor readings that fall outside the normal operating range but within physical limits — may indicate early-stage equipment degradation |
| **Calculation** | `SUM(is_anomaly)` grouped by asset_id per day |
| **Source Tables** | `silver_sensors_clean` |
| **Refresh Frequency** | Daily |
| **Data Quality Dependencies** | Requires valid sensor range configuration per sensor type |
| **Owner** | Reliability Engineering |

## Failure Risk Score

| Field | Value |
|-------|-------|
| **KPI Name** | 7-Day Failure Risk Score |
| **Business Definition** | Predicted probability of equipment failure within the next 7 days, output by the Random Forest classifier |
| **Calculation** | `model.predict_proba(features)[:, 1]` — probability of failure class |
| **Source Tables** | `gold_failure_prediction_features` |
| **Refresh Frequency** | Daily |
| **Data Quality Dependencies** | Requires sensor completeness ≥ 80%; degrades with low-quality sensor inputs |
| **Owner** | Predictive Maintenance Team |

## Mean Time Between Failures (MTBF)

| Field | Value |
|-------|-------|
| **KPI Name** | MTBF per Asset |
| **Business Definition** | Average number of operating hours between consecutive failures for a given asset |
| **Calculation** | `total_operating_hours / failure_count` where operating_hours = days_active × 24 |
| **Source Tables** | `silver_failure_events_clean`, `silver_assets_clean` |
| **Refresh Frequency** | Monthly |
| **Data Quality Dependencies** | Requires complete failure history; maintenance work orders must be closed on time |
| **Owner** | Reliability Engineering |

## Maintenance Urgency Index

| Field | Value |
|-------|-------|
| **KPI Name** | Maintenance Urgency Classification |
| **Business Definition** | Three-tier urgency classification (OVERDUE, DUE_SOON, ON_SCHEDULE) based on days since last maintenance vs scheduled interval |
| **Calculation** | `OVERDUE` if days_since > interval; `DUE_SOON` if days_since > 80% of interval; `ON_SCHEDULE` otherwise |
| **Source Tables** | `gold_asset_health_summary`, `silver_work_orders_clean` |
| **Refresh Frequency** | Daily |
| **Data Quality Dependencies** | Requires completed_date in work orders; null completed_date treated as incomplete |
| **Owner** | Maintenance Planning |
