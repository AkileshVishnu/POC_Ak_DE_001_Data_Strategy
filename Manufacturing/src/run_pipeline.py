"""
Manufacturing Data Pipeline
Orchestrates: Bronze ingestion → Silver time-series validation → Gold asset data products
Implements: timestamp quality checks, sensor range validation, gap detection, rolling features
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
BRONZE_DIR = BASE_DIR / "data" / "bronze"
SILVER_DIR = BASE_DIR / "data" / "silver"
GOLD_DIR = BASE_DIR / "data" / "gold"
DB_PATH = BASE_DIR / "manufacturing.duckdb"

for d in [BRONZE_DIR, SILVER_DIR, GOLD_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def get_connection():
    return duckdb.connect(str(DB_PATH))


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ── Bronze ─────────────────────────────────────────────────────────────────────

def ingest_bronze(con):
    log("=== BRONZE LAYER: Raw Ingestion ===")
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    load_ts = datetime.now().isoformat()

    sources = {
        "bronze_assets": "assets.csv",
        "bronze_sensor_readings": "sensor_readings.csv",
        "bronze_work_orders": "work_orders.csv",
        "bronze_failure_events": "failure_events.csv",
        "bronze_quality_inspections": "quality_inspections.csv",
    }

    for table, filename in sources.items():
        path = RAW_DIR / filename
        if not path.exists():
            log(f"  WARNING: {filename} not found")
            continue
        df = pd.read_csv(path)
        df["_batch_id"] = batch_id
        df["_load_ts"] = load_ts
        df["_source_file"] = filename
        con.execute(f"DROP TABLE IF EXISTS {table}")
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM df")
        df.to_parquet(BRONZE_DIR / f"{table}.parquet", index=False)
        log(f"  ✓ {table}: {len(df):,} rows")


# ── Silver ─────────────────────────────────────────────────────────────────────

def transform_silver(con):
    log("\n=== SILVER LAYER: Time-Series Validation ===")

    # silver_assets_clean
    con.execute("""
        CREATE OR REPLACE TABLE silver_assets_clean AS
        SELECT
            asset_id,
            TRIM(asset_name)            AS asset_name,
            TRIM(asset_type)            AS asset_type,
            TRIM(asset_type_name)       AS asset_type_name,
            production_line,
            criticality,
            CAST(install_date AS DATE)  AS install_date,
            CAST(age_years AS DOUBLE)   AS age_years,
            manufacturer,
            CAST(expected_lifespan_years AS INTEGER) AS expected_lifespan_years,
            CAST(maintenance_interval_days AS INTEGER) AS maintenance_interval_days,
            CAST(is_active AS BOOLEAN)  AS is_active
        FROM bronze_assets
        WHERE asset_id IS NOT NULL
    """)
    log(f"  ✓ silver_assets_clean: {con.execute('SELECT COUNT(*) FROM silver_assets_clean').fetchone()[0]:,}")

    # silver_sensors_clean: Time-series validation layer (most critical)
    log("  Running time-series validation on sensor readings...")
    con.execute("""
        CREATE OR REPLACE TABLE silver_sensors_clean AS
        SELECT
            reading_id,
            sensor_id,
            asset_id,
            sensor_type,
            CAST(reading_timestamp AS TIMESTAMP)    AS reading_timestamp,
            CAST(DATE_TRUNC('hour', CAST(reading_timestamp AS TIMESTAMP)) AS TIMESTAMP)
                                                    AS reading_hour,
            CAST(reading_value AS DOUBLE)           AS reading_value,
            unit,
            CAST(expected_min AS DOUBLE)            AS expected_min,
            CAST(expected_max AS DOUBLE)            AS expected_max,
            CAST(normal_low AS DOUBLE)              AS normal_low,
            CAST(normal_high AS DOUBLE)             AS normal_high,
            -- Timestamp quality checks
            CASE WHEN reading_timestamp <= CURRENT_TIMESTAMP THEN 1 ELSE 0 END
                AS dq_timestamp_not_future,
            CASE WHEN reading_timestamp >= '2022-01-01' THEN 1 ELSE 0 END
                AS dq_timestamp_not_ancient,
            -- Value range validation (physical sensor limits)
            CASE WHEN reading_value BETWEEN expected_min AND expected_max THEN 1 ELSE 0 END
                AS dq_value_in_range,
            -- Normal operating range flag
            CASE WHEN reading_value BETWEEN normal_low AND normal_high THEN 1 ELSE 0 END
                AS in_normal_range,
            -- Anomaly flag: outside normal but within physical limits
            CASE WHEN reading_value NOT BETWEEN normal_low AND normal_high
                      AND reading_value BETWEEN expected_min AND expected_max
                 THEN 1 ELSE 0 END                 AS is_anomaly,
            -- Hard outlier: outside physical limits
            CASE WHEN reading_value < expected_min OR reading_value > expected_max
                 THEN 1 ELSE 0 END                 AS is_hard_outlier,
            -- Overall reading quality (1 = good, 0 = bad)
            CASE WHEN reading_value BETWEEN expected_min AND expected_max
                      AND reading_timestamp <= CURRENT_TIMESTAMP
                 THEN 1 ELSE 0 END                 AS dq_reading_valid,
            _batch_id,
            _load_ts
        FROM bronze_sensor_readings
        WHERE reading_id IS NOT NULL
          AND reading_timestamp IS NOT NULL
    """)
    count = con.execute("SELECT COUNT(*) FROM silver_sensors_clean").fetchone()[0]
    outliers = con.execute("SELECT COUNT(*) FROM silver_sensors_clean WHERE is_hard_outlier = 1").fetchone()[0]
    anomalies = con.execute("SELECT COUNT(*) FROM silver_sensors_clean WHERE is_anomaly = 1").fetchone()[0]
    log(f"  ✓ silver_sensors_clean: {count:,} rows | outliers: {outliers:,} | anomalies: {anomalies:,}")

    # silver_work_orders_clean
    con.execute("""
        CREATE OR REPLACE TABLE silver_work_orders_clean AS
        SELECT
            work_order_id,
            asset_id,
            work_order_type,
            CAST(created_date AS DATE)   AS created_date,
            CAST(completed_date AS DATE) AS completed_date,
            CAST(estimated_hours AS INTEGER) AS estimated_hours,
            CAST(actual_hours AS DOUBLE) AS actual_hours,
            technician_id,
            priority,
            CAST(cost_usd AS DOUBLE)     AS cost_usd,
            parts_replaced,
            DATEDIFF('day', CAST(created_date AS DATE), CAST(completed_date AS DATE))
                AS resolution_days
        FROM bronze_work_orders
        WHERE work_order_id IS NOT NULL
          AND created_date IS NOT NULL
    """)
    log(f"  ✓ silver_work_orders_clean: {con.execute('SELECT COUNT(*) FROM silver_work_orders_clean').fetchone()[0]:,}")

    # silver_failure_events_clean
    con.execute("""
        CREATE OR REPLACE TABLE silver_failure_events_clean AS
        SELECT
            failure_id,
            asset_id,
            failure_type,
            CAST(failure_date AS DATE)  AS failure_date,
            detection_method,
            CAST(downtime_hours AS DOUBLE)  AS downtime_hours,
            CAST(repair_cost_usd AS DOUBLE) AS repair_cost_usd,
            severity,
            root_cause,
            CAST(was_predicted AS BOOLEAN)  AS was_predicted
        FROM bronze_failure_events
        WHERE failure_id IS NOT NULL
    """)
    log(f"  ✓ silver_failure_events_clean: {con.execute('SELECT COUNT(*) FROM silver_failure_events_clean').fetchone()[0]:,}")

    # silver_quality_clean
    con.execute("""
        CREATE OR REPLACE TABLE silver_quality_clean AS
        SELECT
            inspection_id,
            asset_id,
            CAST(inspection_date AS DATE) AS inspection_date,
            CAST(defect_count AS INTEGER) AS defect_count,
            CAST(pass_rate AS DOUBLE)    AS pass_rate,
            CAST(production_volume AS INTEGER) AS production_volume,
            shift,
            product_sku
        FROM bronze_quality_inspections WHERE inspection_id IS NOT NULL
    """)
    log(f"  ✓ silver_quality_clean: {con.execute('SELECT COUNT(*) FROM silver_quality_clean').fetchone()[0]:,}")

    log("Silver time-series validation complete.")


# ── Gold ───────────────────────────────────────────────────────────────────────

def build_gold(con):
    log("\n=== GOLD LAYER: Asset Data Products ===")

    # gold_sensor_quality_score: per-sensor quality metrics
    con.execute("""
        CREATE OR REPLACE TABLE gold_sensor_quality_score AS
        SELECT
            sensor_id,
            asset_id,
            sensor_type,
            COUNT(*)                                          AS total_readings,
            SUM(dq_reading_valid)                            AS valid_readings,
            ROUND(AVG(dq_reading_valid) * 100, 2)            AS validity_rate_pct,
            SUM(is_hard_outlier)                             AS hard_outlier_count,
            ROUND(AVG(is_hard_outlier) * 100, 2)             AS outlier_rate_pct,
            SUM(is_anomaly)                                  AS anomaly_count,
            ROUND(AVG(is_anomaly) * 100, 2)                  AS anomaly_rate_pct,
            MIN(reading_timestamp)                           AS first_reading_ts,
            MAX(reading_timestamp)                           AS last_reading_ts,
            DATEDIFF('hour', MIN(reading_timestamp), MAX(reading_timestamp)) + 1
                                                             AS expected_reading_count,
            -- Sensor quality score: high validity, low outliers, low anomaly rate
            GREATEST(0, LEAST(100,
                AVG(dq_reading_valid) * 60 +
                (1 - AVG(is_hard_outlier)) * 25 +
                (1 - LEAST(1, AVG(is_anomaly) * 5)) * 15
            ))                                               AS sensor_quality_score,
            CURRENT_TIMESTAMP                                AS gold_created_ts
        FROM silver_sensors_clean
        GROUP BY sensor_id, asset_id, sensor_type
    """)
    log(f"  ✓ gold_sensor_quality_score: {con.execute('SELECT COUNT(*) FROM gold_sensor_quality_score').fetchone()[0]:,}")

    # gold_failure_prediction_features: rolling window features per asset per day
    log("  Building rolling window features for failure prediction...")
    con.execute("""
        CREATE OR REPLACE TABLE gold_failure_prediction_features AS
        WITH daily_sensor_stats AS (
            SELECT
                asset_id,
                DATE_TRUNC('day', reading_timestamp)::DATE  AS reading_date,
                sensor_type,
                AVG(CASE WHEN dq_reading_valid = 1 THEN reading_value END) AS daily_avg,
                MAX(CASE WHEN dq_reading_valid = 1 THEN reading_value END) AS daily_max,
                MIN(CASE WHEN dq_reading_valid = 1 THEN reading_value END) AS daily_min,
                STDDEV(CASE WHEN dq_reading_valid = 1 THEN reading_value END) AS daily_std,
                COUNT(CASE WHEN dq_reading_valid = 1 THEN 1 END) AS valid_count,
                COUNT(*) AS total_count,
                SUM(is_anomaly) AS anomaly_count_day,
                SUM(is_hard_outlier) AS outlier_count_day,
                ROUND(COUNT(CASE WHEN dq_reading_valid = 1 THEN 1 END)::DOUBLE /
                      NULLIF(COUNT(*), 0) * 100, 2) AS day_completeness_pct
            FROM silver_sensors_clean
            GROUP BY asset_id, DATE_TRUNC('day', reading_timestamp)::DATE, sensor_type
        ),
        pivoted AS (
            SELECT
                asset_id,
                reading_date,
                AVG(CASE WHEN sensor_type = 'temperature' THEN daily_avg END) AS avg_temp,
                AVG(CASE WHEN sensor_type = 'vibration' THEN daily_avg END)   AS avg_vibration,
                AVG(CASE WHEN sensor_type = 'pressure' THEN daily_avg END)    AS avg_pressure,
                AVG(CASE WHEN sensor_type = 'speed' THEN daily_avg END)       AS avg_speed,
                MAX(CASE WHEN sensor_type = 'temperature' THEN daily_max END) AS max_temp,
                MAX(CASE WHEN sensor_type = 'vibration' THEN daily_max END)   AS max_vibration,
                AVG(CASE WHEN sensor_type = 'temperature' THEN daily_std END) AS std_temp,
                AVG(CASE WHEN sensor_type = 'vibration' THEN daily_std END)   AS std_vibration,
                SUM(anomaly_count_day)  AS total_anomalies_day,
                SUM(outlier_count_day)  AS total_outliers_day,
                AVG(day_completeness_pct) AS sensor_completeness_pct
            FROM daily_sensor_stats
            GROUP BY asset_id, reading_date
        ),
        with_failure_label AS (
            SELECT
                p.*,
                a.asset_type,
                a.age_years,
                a.criticality,
                a.maintenance_interval_days,
                -- Failure within next 7 days (target label)
                CASE WHEN EXISTS (
                    SELECT 1 FROM silver_failure_events_clean f
                    WHERE f.asset_id = p.asset_id
                    AND f.failure_date BETWEEN p.reading_date AND p.reading_date + INTERVAL '7 days'
                ) THEN 1 ELSE 0 END AS failure_in_next_7d,
                -- Days since last maintenance
                COALESCE((
                    SELECT DATEDIFF('day', MAX(w.completed_date), p.reading_date)
                    FROM silver_work_orders_clean w
                    WHERE w.asset_id = p.asset_id
                    AND w.completed_date <= p.reading_date
                ), 999) AS days_since_last_maintenance,
                -- Failure count last 90 days
                COALESCE((
                    SELECT COUNT(*)
                    FROM silver_failure_events_clean f
                    WHERE f.asset_id = p.asset_id
                    AND f.failure_date BETWEEN p.reading_date - INTERVAL '90 days' AND p.reading_date
                ), 0) AS failures_last_90d
            FROM pivoted p
            LEFT JOIN silver_assets_clean a USING (asset_id)
        )
        SELECT
            *,
            CASE criticality WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 ELSE 1 END AS criticality_num,
            CURRENT_TIMESTAMP AS feature_ts
        FROM with_failure_label
        WHERE avg_temp IS NOT NULL OR avg_vibration IS NOT NULL
    """)
    count = con.execute("SELECT COUNT(*) FROM gold_failure_prediction_features").fetchone()[0]
    log(f"  ✓ gold_failure_prediction_features: {count:,} rows")

    # gold_asset_health_summary: per-asset health and risk profile
    con.execute("""
        CREATE OR REPLACE TABLE gold_asset_health_summary AS
        WITH sensor_health AS (
            SELECT
                asset_id,
                AVG(sensor_quality_score)      AS avg_sensor_quality,
                MIN(sensor_quality_score)      AS min_sensor_quality,
                AVG(validity_rate_pct)         AS avg_validity_rate,
                SUM(anomaly_count)             AS total_anomalies,
                SUM(hard_outlier_count)        AS total_outliers
            FROM gold_sensor_quality_score
            GROUP BY asset_id
        ),
        failure_history AS (
            SELECT
                asset_id,
                COUNT(*) AS failure_count_12m,
                SUM(downtime_hours) AS total_downtime_hours,
                MAX(failure_date) AS last_failure_date
            FROM silver_failure_events_clean
            WHERE failure_date >= CURRENT_DATE - INTERVAL '365 days'
            GROUP BY asset_id
        ),
        maintenance_history AS (
            SELECT
                asset_id,
                COUNT(*) AS wo_count_12m,
                SUM(cost_usd) AS total_maintenance_cost,
                MAX(completed_date) AS last_maintenance_date
            FROM silver_work_orders_clean
            WHERE created_date >= CURRENT_DATE - INTERVAL '365 days'
            GROUP BY asset_id
        )
        SELECT
            a.asset_id,
            a.asset_name,
            a.asset_type,
            a.production_line,
            a.criticality,
            a.age_years,
            a.maintenance_interval_days,
            -- Sensor health signals
            COALESCE(s.avg_sensor_quality, 0)       AS avg_sensor_quality_score,
            COALESCE(s.avg_validity_rate, 0)         AS sensor_validity_rate,
            COALESCE(s.total_anomalies, 0)           AS total_sensor_anomalies,
            -- Failure history
            COALESCE(f.failure_count_12m, 0)         AS failure_count_12m,
            COALESCE(f.total_downtime_hours, 0)      AS total_downtime_hours_12m,
            f.last_failure_date,
            DATEDIFF('day', COALESCE(f.last_failure_date, a.install_date), CURRENT_DATE)
                AS days_since_last_failure,
            -- Maintenance history
            COALESCE(m.wo_count_12m, 0)              AS work_orders_12m,
            COALESCE(m.total_maintenance_cost, 0)    AS maintenance_cost_12m_usd,
            m.last_maintenance_date,
            DATEDIFF('day', COALESCE(m.last_maintenance_date, a.install_date), CURRENT_DATE)
                AS days_since_last_maintenance,
            -- Asset health score (0-100)
            GREATEST(0, LEAST(100,
                COALESCE(s.avg_sensor_quality, 50) * 0.4 +
                GREATEST(0, 100 - COALESCE(f.failure_count_12m, 0) * 20) * 0.3 +
                GREATEST(0, 100 - (a.age_years / NULLIF(a.expected_lifespan_years, 0)) * 100) * 0.3
            )) AS asset_health_score,
            -- Maintenance urgency
            CASE
                WHEN DATEDIFF('day', COALESCE(m.last_maintenance_date, a.install_date), CURRENT_DATE)
                     > a.maintenance_interval_days THEN 'OVERDUE'
                WHEN DATEDIFF('day', COALESCE(m.last_maintenance_date, a.install_date), CURRENT_DATE)
                     > a.maintenance_interval_days * 0.8 THEN 'DUE_SOON'
                ELSE 'ON_SCHEDULE'
            END AS maintenance_urgency,
            CURRENT_TIMESTAMP AS gold_created_ts
        FROM silver_assets_clean a
        LEFT JOIN sensor_health s USING (asset_id)
        LEFT JOIN failure_history f USING (asset_id)
        LEFT JOIN maintenance_history m USING (asset_id)
    """)
    log(f"  ✓ gold_asset_health_summary: {con.execute('SELECT COUNT(*) FROM gold_asset_health_summary').fetchone()[0]:,}")

    # gold_maintenance_recommendations: prioritized maintenance queue
    con.execute("""
        CREATE OR REPLACE TABLE gold_maintenance_recommendations AS
        SELECT
            asset_id,
            asset_name,
            asset_type,
            production_line,
            criticality,
            asset_health_score,
            maintenance_urgency,
            days_since_last_maintenance,
            maintenance_interval_days,
            failure_count_12m,
            total_downtime_hours_12m,
            avg_sensor_quality_score,
            total_sensor_anomalies,
            -- Priority score: higher = more urgent
            ROUND(
                CASE criticality WHEN 'HIGH' THEN 40 WHEN 'MEDIUM' THEN 25 ELSE 10 END +
                CASE maintenance_urgency WHEN 'OVERDUE' THEN 30 WHEN 'DUE_SOON' THEN 15 ELSE 0 END +
                GREATEST(0, 100 - asset_health_score) * 0.2 +
                LEAST(failure_count_12m * 5, 20)
            , 1) AS maintenance_priority_score,
            CASE
                WHEN asset_health_score < 30 AND criticality = 'HIGH' THEN 'EMERGENCY'
                WHEN asset_health_score < 50 OR maintenance_urgency = 'OVERDUE' THEN 'HIGH'
                WHEN maintenance_urgency = 'DUE_SOON' THEN 'MEDIUM'
                ELSE 'LOW'
            END AS recommended_action_tier,
            CURRENT_TIMESTAMP AS gold_created_ts
        FROM gold_asset_health_summary
        ORDER BY maintenance_priority_score DESC
    """)
    log(f"  ✓ gold_maintenance_recommendations: {con.execute('SELECT COUNT(*) FROM gold_maintenance_recommendations').fetchone()[0]:,}")

    # Export Gold tables
    for table in ["gold_asset_health_summary", "gold_sensor_quality_score",
                  "gold_failure_prediction_features", "gold_maintenance_recommendations"]:
        df = con.execute(f"SELECT * FROM {table}").df()
        df.to_parquet(GOLD_DIR / f"{table}.parquet", index=False)
        log(f"  → Exported {table}.parquet")

    log("Gold layer complete.")


def main():
    log("Starting Manufacturing Data Pipeline")
    con = get_connection()
    try:
        ingest_bronze(con)
        transform_silver(con)
        build_gold(con)
        log("\nPipeline completed successfully.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
