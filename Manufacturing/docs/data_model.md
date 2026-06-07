# Manufacturing Data Model

## Entity Relationships

```
Asset (master entity)
  ├── Sensor Readings (many, hourly, per sensor type)
  ├── Work Orders (many, maintenance events)
  ├── Failure Events (many, unplanned outages)
  └── Quality Inspections (many, production quality records)
```

## Key Tables

### gold_failure_prediction_features (Primary ML Input)

| Column | Type | Description |
|--------|------|-------------|
| asset_id | VARCHAR | Asset identifier |
| reading_date | DATE | Date of feature window |
| avg_temp | DOUBLE | Daily avg temperature (valid readings only) |
| avg_vibration | DOUBLE | Daily avg vibration |
| avg_pressure | DOUBLE | Daily avg pressure |
| avg_speed | DOUBLE | Daily avg speed (RPM) |
| max_temp | DOUBLE | Daily max temperature |
| max_vibration | DOUBLE | Daily max vibration |
| std_temp | DOUBLE | Daily temperature variability |
| std_vibration | DOUBLE | Daily vibration variability |
| total_anomalies_day | INTEGER | Sensor readings outside normal range |
| total_outliers_day | INTEGER | Hard outlier count |
| sensor_completeness_pct | DOUBLE | % of expected readings received |
| asset_type | VARCHAR | Equipment type |
| age_years | DOUBLE | Asset age |
| criticality | VARCHAR | HIGH / MEDIUM / LOW |
| criticality_num | INTEGER | Encoded criticality (3/2/1) |
| maintenance_interval_days | INTEGER | Scheduled maintenance cadence |
| days_since_last_maintenance | INTEGER | Days since last work order completion |
| failures_last_90d | INTEGER | Failure count in prior 90 days |
| failure_in_next_7d | INTEGER | Label: 1 if failure occurs within 7 days |
| feature_ts | TIMESTAMP | Feature computation timestamp |

### gold_asset_health_summary

| Column | Type | Description |
|--------|------|-------------|
| asset_id | VARCHAR | Asset ID |
| asset_name | VARCHAR | Human-readable name |
| asset_type | VARCHAR | Equipment type code |
| production_line | VARCHAR | Production line assignment |
| criticality | VARCHAR | Business criticality |
| age_years | DOUBLE | Asset age in years |
| avg_sensor_quality_score | DOUBLE | Average sensor quality across all sensors |
| sensor_validity_rate | DOUBLE | % of readings that passed range check |
| total_sensor_anomalies | INTEGER | Cumulative anomaly count |
| failure_count_12m | INTEGER | Failures in last 12 months |
| total_downtime_hours_12m | DOUBLE | Total downtime hours (12m) |
| days_since_last_failure | INTEGER | Days since most recent failure |
| work_orders_12m | INTEGER | Work orders in last 12 months |
| maintenance_cost_12m_usd | DOUBLE | Total maintenance cost (12m) |
| days_since_last_maintenance | INTEGER | Days since last completed WO |
| asset_health_score | DOUBLE | Composite health score (0–100) |
| maintenance_urgency | VARCHAR | OVERDUE / DUE_SOON / ON_SCHEDULE |

### gold_sensor_quality_score

| Column | Type | Description |
|--------|------|-------------|
| sensor_id | VARCHAR | Sensor identifier |
| asset_id | VARCHAR | Parent asset |
| sensor_type | VARCHAR | temperature / vibration / pressure / speed |
| total_readings | INTEGER | Total readings received |
| valid_readings | INTEGER | Readings passing all quality checks |
| validity_rate_pct | DOUBLE | % valid readings |
| hard_outlier_count | INTEGER | Readings outside physical limits |
| outlier_rate_pct | DOUBLE | % hard outliers |
| anomaly_count | INTEGER | Readings outside normal but within limits |
| anomaly_rate_pct | DOUBLE | % anomalous readings |
| sensor_quality_score | DOUBLE | Composite quality score (0–100) |
| first_reading_ts | TIMESTAMP | Oldest reading |
| last_reading_ts | TIMESTAMP | Most recent reading |
