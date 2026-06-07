# Manufacturing Data Strategy: Time-Series Quality and Asset Data Product

## Why Time-Series Data Strategy Differs from All Others

Manufacturing data has unique characteristics that make generic data strategies insufficient:

1. **High frequency**: Sensors emit readings every minute or second — far higher velocity than transactional systems
2. **Physical constraints**: Sensor values must respect physics (temperature cannot be -300°C)
3. **Temporal ordering matters**: In time-series data, the sequence of readings carries meaning — a model that ignores ordering misses failure progression patterns
4. **Sensor degradation**: Unlike databases, sensors physically degrade, drift, and fail — the data itself can go bad invisibly
5. **Rolling context required**: A single reading is rarely meaningful; the pattern over time is what matters for predictive maintenance

An MDM strategy (Healthcare) or point-in-time feature strategy (Finance) does not address these needs. Manufacturing needs a **time-series quality and asset hierarchy** strategy.

---

## Source System Strategy

| Source System | Data | Protocol | Challenges |
|--------------|------|----------|-----------|
| SCADA | Sensor readings | OPC-UA, Modbus | Clock drift, packet loss, buffering |
| CMMS | Work orders, maintenance history | REST API | Manual data entry quality |
| ERP | Asset registry, parts inventory | Database extract | SCD management |
| Quality System | Inspection results, defect logs | CSV export | Inconsistent defect coding |
| Historian | Long-term sensor archive | PI Historian | Time alignment, gap handling |

### Timestamp Challenges in SCADA Data

SCADA systems aggregate sensor readings from field devices, which have their own clocks. Common issues:
- **Clock skew**: Field device clock diverges from SCADA server clock (up to ±6 hours)
- **Buffering**: Readings stored locally and uploaded in batches may have timestamps reflecting storage time, not measurement time
- **Daylight saving**: Industrial systems often don't handle DST correctly, creating 1-hour jumps

**Resolution strategy**: Record both `device_timestamp` (from field device) and `ingestion_timestamp` (when received). Use device_timestamp with a maximum offset filter (reject readings >8 hours in the future or past).

---

## Data Quality Strategy

### Sensor Range Validation

Every sensor type has a defined valid range and a normal operating range:

| Sensor | Physical Min | Physical Max | Normal Low | Normal High | Action if Outside Normal |
|--------|-------------|-------------|-----------|------------|------------------------|
| Temperature | -20°C | 200°C | 40°C | 80°C | Flag anomaly; do not exclude |
| Vibration | 0 mm/s | 100 mm/s | 0 mm/s | 15 mm/s | Flag anomaly; do not exclude |
| Pressure | 0 bar | 300 bar | 10 bar | 80 bar | Flag anomaly; do not exclude |
| Speed | 0 RPM | 8000 RPM | 500 RPM | 3000 RPM | Flag anomaly; do not exclude |

**Key design decision**: Readings outside the normal range are flagged, not excluded. They may carry the most valuable signal for failure prediction. Only readings outside physical limits are excluded.

### Gap Detection

A sensor gap is defined as a period of expected readings where none were received.

For hourly sensors: a gap is any 2+ consecutive hours with no readings.

Gap detection is implemented at the Silver layer:
```sql
-- Detect hours with no readings (gap)
SELECT
  sensor_id,
  reading_hour,
  LAG(reading_hour) OVER (PARTITION BY sensor_id ORDER BY reading_hour) AS prev_hour,
  DATEDIFF('hour', LAG(reading_hour) OVER (...), reading_hour) - 1 AS gap_hours_before
FROM silver_sensors_clean
```

### Sensor Quality Score

Each sensor receives a composite quality score (0–100):
- **Validity rate** (60% weight): What fraction of readings pass range validation?
- **Outlier rate** (25% weight): What fraction of readings are hard outliers?
- **Anomaly rate** (15% weight): Penalize high anomaly rates moderately (anomalies may be real signal)

A sensor with quality score < 60 is flagged in the feature layer. Rolling features derived from it carry a reduced confidence flag.

---

## Data Governance Strategy

### Asset Master Data

The asset hierarchy is the foundational reference data:
```
Production Plant
  └── Production Line (LINE_A, LINE_B, ...)
        └── Asset (ASSET_0001, ...)
              └── Sensor (SEN_000001, ...)
```

Changes to this hierarchy must be managed as Slowly Changing Dimensions (SCD Type 2) to preserve historical sensor-to-asset relationships.

### Maintenance Record Governance

Work order data from CMMS is subject to:
- **Completeness enforcement**: All work orders must have created_date and asset_id
- **Completion tracking**: Open work orders are flagged; overdue work orders escalate to management
- **Cost validation**: Work order cost must be within ±50% of estimate for data quality acceptance

---

## Feature Engineering Strategy

### Rolling Window Design

All rolling features are computed over validated sensor readings:

| Feature | Window | Aggregation | Gap Handling |
|---------|--------|-------------|-------------|
| avg_temp | 24h | MEAN of valid readings | NULL if completeness < 50% |
| std_vibration | 24h | STDDEV of valid readings | NULL if completeness < 50% |
| max_temp | 24h | MAX of valid readings | NULL if completeness < 50% |
| total_anomalies_day | 24h | COUNT of anomaly flags | 0 if no anomalies detected |
| sensor_completeness_pct | 24h | valid_count / expected_count | Always computed |

### Why Rolling Features Require Gap-Awareness

A naive rolling average computed over gappy data is misleading:

```
Hour 1: 72°C
Hour 2: MISSING (gap)
Hour 3: MISSING (gap)
Hour 4: 95°C (failure approaching)

Naive 4h average: (72 + 95) / 2 = 83.5°C
Gap-aware 4h average: (72 + 95) / 4 = 41.75°C — WRONG
Correct approach: flag window as incomplete; report completeness_pct = 50%
```

---

## AI Consumption Strategy

### Feature Gating

Features derived from low-quality sensors are gated:
- If `sensor_quality_score < 60` → feature flagged with `low_confidence = true`
- If `sensor_completeness_pct < 50%` → rolling features set to NULL
- Model receives quality scores as input features so it can learn to discount low-quality signals

### Prediction Horizon

The 7-day prediction horizon is chosen because:
- It gives maintenance teams enough time to schedule parts and technicians
- It is short enough that the failure signal is still detectable in current sensor data
- Shorter horizons (1-2 days) are too late for maintenance planning
- Longer horizons (30+ days) have too much noise to be reliable

---

## Observability Strategy

| Signal | Monitored | Threshold | Action |
|--------|----------|-----------|--------|
| Sensor missingness rate | Daily | > 5% of expected readings | Alert Data Engineering |
| Hard outlier rate | Daily | > 2% of readings | Investigate sensor health |
| Anomaly rate trend | Weekly | Increasing 10% week-over-week | Investigate equipment |
| Asset health score drop | Daily | Drop > 20 points in 7d | Trigger maintenance review |
| Model prediction coverage | Daily | < 95% of active assets | Pipeline failure investigation |
| Failure detection lead time | Monthly | < 2 days average | Model retraining required |
