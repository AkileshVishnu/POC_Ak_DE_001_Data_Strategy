# Manufacturing Data Lineage

## Source to Bronze Mapping

| Source File | Bronze Table | Key Columns | Metadata |
|-------------|-------------|------------|---------|
| sensor_readings.csv | bronze_sensor_readings | sensor_id, asset_id, reading_timestamp, reading_value | _batch_id, _load_ts |
| assets.csv | bronze_assets | asset_id, asset_type, install_date, criticality | _batch_id, _load_ts |
| work_orders.csv | bronze_work_orders | work_order_id, asset_id, created_date, completed_date | _batch_id, _load_ts |
| failure_events.csv | bronze_failure_events | failure_id, asset_id, failure_date, severity | _batch_id, _load_ts |
| quality_inspections.csv | bronze_quality_inspections | inspection_id, asset_id, pass_rate, defect_count | _batch_id, _load_ts |

## Bronze to Silver Transformations

### Critical: Sensor Reading Validation Chain

```
bronze_sensor_readings
  → TYPE CAST: reading_timestamp → TIMESTAMP
  → TIMESTAMP QUALITY:
      dq_timestamp_not_future  = reading_timestamp <= CURRENT_TIMESTAMP
      dq_timestamp_not_ancient = reading_timestamp >= 2022-01-01
  → VALUE RANGE VALIDATION:
      dq_value_in_range = reading_value BETWEEN expected_min AND expected_max
  → ANOMALY DETECTION:
      in_normal_range = reading_value BETWEEN normal_low AND normal_high
      is_anomaly = NOT in_normal_range AND dq_value_in_range (within physical limits but unusual)
      is_hard_outlier = reading_value < expected_min OR > expected_max
  → HOUR TRUNCATION:
      reading_hour = DATE_TRUNC('hour', reading_timestamp)
  → silver_sensors_clean
```

Every record in `silver_sensors_clean` carries all quality flags so they can be propagated to Gold and ML layers.

## Silver to Gold Transformations

### gold_sensor_quality_score Lineage

```
silver_sensors_clean
  GROUP BY sensor_id, asset_id, sensor_type
  → COUNT(valid_readings) / COUNT(*) → validity_rate_pct
  → SUM(is_hard_outlier) → hard_outlier_count
  → SUM(is_anomaly) → anomaly_count
  → COMPOSITE: 60% validity + 25% non-outlier + 15% low-anomaly → sensor_quality_score
  → gold_sensor_quality_score
```

### gold_failure_prediction_features Lineage

```
silver_sensors_clean (per asset per day, valid readings only)
  → PIVOT by sensor_type: temperature, vibration, pressure, speed
  → AGGREGATE: AVG, MAX, STDDEV per day per asset
  → COMPUTE: sensor_completeness_pct = valid_readings / total_readings

  + silver_failure_events_clean
  → SUBQUERY: does a failure occur in the 7 days AFTER this date?
  → failure_in_next_7d (binary label)

  + silver_work_orders_clean
  → SUBQUERY: days since last completed work order (before this date)
  → days_since_last_maintenance

  + silver_assets_clean (static attributes)
  → age_years, criticality, maintenance_interval_days

  → gold_failure_prediction_features (one row per asset per day)
```

## Gold to ML/Dashboard Consumption

| Gold Table | Consumer | Columns Used |
|-----------|---------|-------------|
| gold_failure_prediction_features | train_model.py | FEATURE_COLS + failure_in_next_7d |
| gold_asset_health_summary | streamlit_app.py | All columns |
| gold_sensor_quality_score | streamlit_app.py | All columns |
| gold_maintenance_recommendations | streamlit_app.py | All columns (ordered by priority) |

## Example Lineage: Failure Prediction for ASSET_0012

```
Prediction: ASSET_0012 — failure_probability = 0.78

Feature: avg_vibration = 18.4 mm/s (above normal range of 15)
  gold_failure_prediction_features.avg_vibration
  = AVG(CASE WHEN dq_reading_valid = 1 THEN reading_value END)
    WHERE asset_id = ASSET_0012
    AND sensor_type = 'vibration'
    AND reading_hour BETWEEN 2024-05-15 00:00 AND 2024-05-15 23:00
  
  reading values:
  ← silver_sensors_clean (8 readings on 2024-05-15, all dq_reading_valid = 1)
  ← bronze_sensor_readings (batch_id: 20240515_060000)
  ← sensor_readings.csv (SCADA export 2024-05-15)

Feature: total_anomalies_day = 6 (readings outside normal range)
  ← SUM(is_anomaly) from silver_sensors_clean on 2024-05-15
  ← bronze_sensor_readings same batch

Feature: failure_in_next_7d = 1 (label)
  ← silver_failure_events_clean WHERE asset_id = ASSET_0012
    AND failure_date BETWEEN 2024-05-15 AND 2024-05-22
  ← bronze_failure_events (failure_id: FAIL_00087, failure_date: 2024-05-19)

Feature: days_since_last_maintenance = 87
  ← silver_work_orders_clean WHERE asset_id = ASSET_0012
    AND completed_date <= 2024-05-15
    MAX(completed_date) = 2024-02-18

Conclusion: high vibration trend + 6 daily anomalies + 87 days since maintenance
            → 78% probability of failure in next 7 days → EMERGENCY maintenance recommended
```
