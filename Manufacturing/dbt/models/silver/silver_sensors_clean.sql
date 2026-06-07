-- Silver Sensors Clean: Time-series validated sensor readings
-- Applies timestamp quality checks, range validation, anomaly detection

SELECT
    reading_id,
    sensor_id,
    asset_id,
    sensor_type,
    CAST(reading_timestamp AS TIMESTAMP)    AS reading_timestamp,
    DATE_TRUNC('hour', CAST(reading_timestamp AS TIMESTAMP))::TIMESTAMP AS reading_hour,
    CAST(reading_value AS DOUBLE)           AS reading_value,
    unit,
    CAST(expected_min AS DOUBLE)            AS expected_min,
    CAST(expected_max AS DOUBLE)            AS expected_max,
    CAST(normal_low AS DOUBLE)              AS normal_low,
    CAST(normal_high AS DOUBLE)             AS normal_high,
    -- Timestamp quality flags
    CASE WHEN reading_timestamp <= CURRENT_TIMESTAMP THEN 1 ELSE 0 END AS dq_timestamp_not_future,
    CASE WHEN reading_timestamp >= '2022-01-01' THEN 1 ELSE 0 END      AS dq_timestamp_not_ancient,
    -- Value range validation
    CASE WHEN reading_value BETWEEN expected_min AND expected_max THEN 1 ELSE 0 END AS dq_value_in_range,
    CASE WHEN reading_value BETWEEN normal_low AND normal_high THEN 1 ELSE 0 END   AS in_normal_range,
    -- Anomaly: outside normal range but within physical limits
    CASE
        WHEN reading_value NOT BETWEEN normal_low AND normal_high
         AND reading_value BETWEEN expected_min AND expected_max
        THEN 1 ELSE 0
    END AS is_anomaly,
    -- Hard outlier: violates physical limits
    CASE
        WHEN reading_value < expected_min OR reading_value > expected_max
        THEN 1 ELSE 0
    END AS is_hard_outlier,
    -- Overall reading validity
    CASE
        WHEN reading_value BETWEEN expected_min AND expected_max
         AND reading_timestamp <= CURRENT_TIMESTAMP
        THEN 1 ELSE 0
    END AS dq_reading_valid,
    _batch_id,
    _load_ts
FROM {{ source('bronze', 'bronze_sensor_readings') }}
WHERE reading_id IS NOT NULL
  AND reading_timestamp IS NOT NULL
