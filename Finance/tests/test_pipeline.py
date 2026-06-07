"""
Finance Pipeline Tests
Tests data generation, pipeline integrity, point-in-time correctness, and Gold layer quality.
"""

import pytest
import duckdb
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "finance.duckdb"


@pytest.fixture(scope="session")
def con():
    if not DB_PATH.exists():
        pytest.skip("Database not found. Run `python src/run_pipeline.py` first.")
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    yield conn
    conn.close()


class TestBronzeLayer:
    def test_bronze_transactions_exist(self, con):
        count = con.execute("SELECT COUNT(*) FROM bronze_transactions").fetchone()[0]
        assert count >= 50000

    def test_bronze_has_metadata(self, con):
        cols = con.execute("DESCRIBE bronze_transactions").df()["column_name"].tolist()
        assert "_batch_id" in cols
        assert "_load_ts" in cols

    def test_bronze_fraud_labels_present(self, con):
        count = con.execute("SELECT COUNT(*) FROM bronze_transactions WHERE is_fraud = true").fetchone()[0]
        assert count > 0, "Expected some fraud labels"


class TestSilverLayer:
    def test_silver_transactions_no_future_dates(self, con):
        future = con.execute("""
            SELECT COUNT(*) FROM silver_transactions_clean
            WHERE transaction_date > CURRENT_DATE
        """).fetchone()[0]
        assert future == 0

    def test_silver_transactions_positive_amounts(self, con):
        neg = con.execute("""
            SELECT COUNT(*) FROM silver_transactions_clean WHERE amount <= 0
        """).fetchone()[0]
        assert neg == 0

    def test_silver_customers_no_duplicates(self, con):
        dupes = con.execute("""
            SELECT COUNT(*) FROM (
                SELECT customer_id, COUNT(*) c FROM silver_customers_clean GROUP BY 1 HAVING c > 1
            )
        """).fetchone()[0]
        assert dupes == 0


class TestPointInTimeCorrectness:
    """Critical tests: verify point-in-time feature correctness."""

    def test_pit_no_future_data_in_30d_window(self, con):
        """Verify that 30-day rolling features do not use data after the transaction date."""
        violations = con.execute("""
            SELECT COUNT(*) FROM gold_transaction_risk_features
            WHERE days_since_last_tx < 0
        """).fetchone()[0]
        assert violations == 0, "Negative days_since_last_tx indicates future data usage"

    def test_pit_features_have_timestamp(self, con):
        """All features must have a feature_ts indicating when they were computed."""
        null_ts = con.execute("""
            SELECT COUNT(*) FROM gold_transaction_risk_features WHERE feature_ts IS NULL
        """).fetchone()[0]
        assert null_ts == 0

    def test_pit_prior_fraud_count_non_negative(self, con):
        neg = con.execute("""
            SELECT COUNT(*) FROM gold_transaction_risk_features WHERE prior_fraud_count < 0
        """).fetchone()[0]
        assert neg == 0

    def test_pit_amount_vs_avg_ratio_non_negative(self, con):
        neg = con.execute("""
            SELECT COUNT(*) FROM gold_transaction_risk_features WHERE amount_vs_avg_ratio < 0
        """).fetchone()[0]
        assert neg == 0


class TestGoldLayer:
    def test_gold_customer_360_count(self, con):
        count = con.execute("SELECT COUNT(*) FROM gold_customer_360").fetchone()[0]
        assert count >= 1000

    def test_gold_features_bureau_score_range(self, con):
        out_range = con.execute("""
            SELECT COUNT(*) FROM gold_transaction_risk_features
            WHERE bureau_score < 300 OR bureau_score > 850
        """).fetchone()[0]
        assert out_range == 0

    def test_gold_risk_profile_tier_not_null(self, con):
        nulls = con.execute("""
            SELECT COUNT(*) FROM gold_customer_risk_profile WHERE risk_tier IS NULL
        """).fetchone()[0]
        assert nulls == 0

    def test_gold_fraud_rate_realistic(self, con):
        rate = con.execute("""
            SELECT AVG(CAST(is_fraud AS DOUBLE)) * 100 FROM gold_transaction_risk_features
        """).fetchone()[0]
        assert 0.5 <= rate <= 10, f"Unrealistic fraud rate: {rate:.2f}%"


class TestDataGeneration:
    def test_raw_files_exist(self):
        raw_dir = BASE_DIR / "data" / "raw"
        for fname in ["customers.csv", "transactions.csv", "merchants.csv",
                       "chargebacks.csv", "bureau_attributes.csv"]:
            assert (raw_dir / fname).exists(), f"Missing: {fname}"

    def test_no_real_account_numbers(self):
        raw_dir = BASE_DIR / "data" / "raw"
        df = pd.read_csv(raw_dir / "accounts.csv")
        assert "ssn" not in df.columns
        assert "routing_number" not in df.columns

    def test_transactions_have_fraud_labels(self):
        raw_dir = BASE_DIR / "data" / "raw"
        df = pd.read_csv(raw_dir / "transactions.csv")
        assert "is_fraud" in df.columns
        assert df["is_fraud"].sum() > 0
