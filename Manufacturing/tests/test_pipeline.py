"""
Manufacturing Pipeline Tests
Tests time-series validation, sensor quality, and Gold layer integrity.
"""

import pytest
import duckdb
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "manufacturing.duckdb"


@pytest.fixture(scope="session")
def con():
    if not DB_PATH.exists():
        pytest.skip("Database not found. Run `python src/run_pipeline.py` first.")
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    yield conn
    conn.close()


class TestBronzeLayer:
    def test_bronze_sensors_exist(self, con):
        count = con.execute("SELECT COUNT(*) FROM bronze_sensor_readings").fetchone()[0]
        assert count > 0

    def test_bronze_assets_exist(self, con):
        count = con.execute("SELECT COUNT(*) FROM bronze_assets").fetchone()[0]
        assert count >= 50

    def test_bronze_has_metadata(self, con):
        cols = con.execute("DESCRIBE bronze_sensor_readings").df()["column_name"].tolist()
        assert "_batch_id" in cols
        assert "_load_ts" in cols


class TestTimestampQuality:
    """Critical tests for time-series timestamp integrity."""

    def test_no_future_timestamps(self, con):
        future = con.execute("""
            SELECT COUNT(*) FROM silver_sensors_clean
            WHERE dq_timestamp_not_future = 0
        """).fetchone()[0]
        total = con.execute("SELECT COUNT(*) FROM silver_sensors_clean").fetchone()[0]
        future_pct = future / total * 100 if total > 0 else 0
        assert future_pct < 1, f"Too many future timestamps: {future_pct:.2f}%"

    def test_timestamp_quality_flag_present(self, con):
        result = con.execute("""
            SELECT COUNT(*) FROM silver_sensors_clean
            WHERE dq_timestamp_not_future IS NULL
        """).fetchone()[0]
        assert result == 0, "Timestamp quality flag must not be null"


class TestSensorQuality:
    def test_sensor_range_validation_present(self, con):
        result = con.execute("""
            SELECT COUNT(*) FROM silver_sensors_clean
            WHERE dq_value_in_range IS NULL
        """).fetchone()[0]
        assert result == 0, "Value range flag must not be null"

    def test_hard_outlier_flagged(self, con):
        result = con.execute("""
            SELECT COUNT(*) FROM silver_sensors_clean WHERE is_hard_outlier IS NOT NULL
        """).fetchone()[0]
        assert result > 0

    def test_anomaly_flagged(self, con):
        result = con.execute("""
            SELECT COUNT(*) FROM silver_sensors_clean WHERE is_anomaly IS NOT NULL
        """).fetchone()[0]
        assert result > 0

    def test_sensor_quality_score_range(self, con):
        out_range = con.execute("""
            SELECT COUNT(*) FROM gold_sensor_quality_score
            WHERE sensor_quality_score < 0 OR sensor_quality_score > 100
        """).fetchone()[0]
        assert out_range == 0, "Sensor quality scores must be in [0, 100]"


class TestGoldLayer:
    def test_gold_asset_health_all_active_assets(self, con):
        asset_count = con.execute("SELECT COUNT(*) FROM silver_assets_clean").fetchone()[0]
        health_count = con.execute("SELECT COUNT(*) FROM gold_asset_health_summary").fetchone()[0]
        assert health_count == asset_count, "All assets must have health summary"

    def test_gold_asset_health_score_range(self, con):
        out_range = con.execute("""
            SELECT COUNT(*) FROM gold_asset_health_summary
            WHERE asset_health_score < 0 OR asset_health_score > 100
        """).fetchone()[0]
        assert out_range == 0

    def test_gold_features_failure_label_binary(self, con):
        invalid = con.execute("""
            SELECT COUNT(*) FROM gold_failure_prediction_features
            WHERE failure_in_next_7d NOT IN (0, 1)
        """).fetchone()[0]
        assert invalid == 0

    def test_gold_sensor_completeness_non_negative(self, con):
        neg = con.execute("""
            SELECT COUNT(*) FROM gold_failure_prediction_features
            WHERE sensor_completeness_pct < 0
        """).fetchone()[0]
        assert neg == 0

    def test_gold_maintenance_recommendations_ordered(self, con):
        top = con.execute("""
            SELECT maintenance_priority_score FROM gold_maintenance_recommendations
            ORDER BY maintenance_priority_score DESC LIMIT 5
        """).df()
        scores = top["maintenance_priority_score"].tolist()
        assert scores == sorted(scores, reverse=True), "Recommendations must be ordered by priority"


class TestDataGeneration:
    def test_raw_sensor_file_exists(self):
        assert (BASE_DIR / "data" / "raw" / "sensor_readings.csv").exists()

    def test_raw_assets_file_exists(self):
        assert (BASE_DIR / "data" / "raw" / "assets.csv").exists()

    def test_sensor_data_has_required_columns(self):
        df = pd.read_csv(BASE_DIR / "data" / "raw" / "sensor_readings.csv")
        required = ["sensor_id", "asset_id", "sensor_type", "reading_timestamp",
                    "reading_value", "expected_min", "expected_max"]
        for col in required:
            assert col in df.columns, f"Missing column: {col}"

    def test_synthetic_data_has_quality_issues(self):
        """Verify data has intentional quality issues for POC demonstration."""
        df = pd.read_csv(BASE_DIR / "data" / "raw" / "sensor_readings.csv")
        assert "has_drift" in df.columns or "is_outlier" in df.columns, \
            "Data should contain injected quality issues"
