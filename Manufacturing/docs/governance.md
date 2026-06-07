# Manufacturing Data Governance

## Sensitive Data Handling

Manufacturing sensor data is synthetic and does not represent real equipment or facilities. No proprietary sensor configurations, production volumes, or operational parameters from real facilities are included.

### Data Classification

| Data Type | Classification | Handling |
|-----------|---------------|---------|
| Sensor readings | OPERATIONAL | Time-series validated; quality-scored |
| Asset registry | INTERNAL | SCD Type 2 tracking for changes |
| Work order costs | FINANCIAL | Accessible to Plant Operations only |
| Failure events | OPERATIONAL | Root cause analysis reports |
| Production volumes | CONFIDENTIAL | Aggregated in quality inspections |

## Access Control

| Data Asset | Authorized Roles |
|-----------|-----------------|
| bronze_sensor_readings | Data Engineering, SCADA Integration |
| silver_sensors_clean | Data Engineering, Analytics |
| gold_asset_health_summary | Operations, Maintenance, Management |
| gold_maintenance_recommendations | Maintenance Team, Operations Management |
| gold_failure_prediction_features | ML Engineering, Data Science |

## Auditability

Every maintenance recommendation is fully traceable:
1. `gold_maintenance_recommendations.asset_id` → `gold_asset_health_summary.asset_id`
2. `gold_asset_health_summary` ← `gold_sensor_quality_score` (sensor health input)
3. `gold_sensor_quality_score` ← `silver_sensors_clean` (validated readings)
4. `silver_sensors_clean` ← `bronze_sensor_readings._batch_id` → ingestion log

## Compliance Considerations

| Standard | Relevance | Status |
|---------|-----------|--------|
| ISO 9001 | Quality management system | Inspection records linked to asset |
| ISO 55001 | Asset management | Asset lifecycle documented |
| IEC 62443 | Industrial cybersecurity | SCADA data handling documented |
| OSHA | Equipment safety records | Work order history maintained |

## Limitations

- Sensor readings are synthetic; no real SCADA or PI Historian data
- Clock skew is injected synthetically to demonstrate detection capability
- Failure labels are rule-based, not from real maintenance event data
- Production DuckDB would be replaced by Databricks or Snowflake at scale
