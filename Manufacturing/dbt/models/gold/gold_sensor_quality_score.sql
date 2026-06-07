-- Gold Sensor Quality Score: Per-sensor quality metrics
-- Composite quality score gates sensor data use in ML features

SELECT
    sensor_id,
    asset_id,
    sensor_type,
    COUNT(*)                                              AS total_readings,
    SUM(dq_reading_valid)                                AS valid_readings,
    ROUND(AVG(dq_reading_valid) * 100, 2)                AS validity_rate_pct,
    SUM(is_hard_outlier)                                 AS hard_outlier_count,
    ROUND(AVG(is_hard_outlier) * 100, 2)                 AS outlier_rate_pct,
    SUM(is_anomaly)                                      AS anomaly_count,
    ROUND(AVG(is_anomaly) * 100, 2)                      AS anomaly_rate_pct,
    MIN(reading_timestamp)                               AS first_reading_ts,
    MAX(reading_timestamp)                               AS last_reading_ts,
    -- Composite quality score (0–100)
    GREATEST(0, LEAST(100,
        AVG(dq_reading_valid) * 60 +
        (1 - AVG(is_hard_outlier)) * 25 +
        (1 - LEAST(1, AVG(is_anomaly) * 5)) * 15
    ))                                                   AS sensor_quality_score,
    CURRENT_TIMESTAMP                                    AS gold_created_ts
FROM {{ ref('silver_sensors_clean') }}
GROUP BY sensor_id, asset_id, sensor_type
