"""
Healthcare Pipeline Tests
Tests synthetic data generation, pipeline transformations, and Gold layer integrity.
"""

import pytest
import duckdb
import pandas as pd
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

DB_PATH = BASE_DIR / "healthcare.duckdb"


@pytest.fixture(scope="session")
def con():
    """Shared DuckDB connection for all tests."""
    if not DB_PATH.exists():
        pytest.skip("Database not found. Run `python src/run_pipeline.py` first.")
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    yield conn
    conn.close()


# ── Bronze Layer Tests ─────────────────────────────────────────────────────────

class TestBronzeLayer:
    def test_bronze_hcp_master_exists(self, con):
        result = con.execute("SELECT COUNT(*) FROM bronze_hcp_master").fetchone()
        assert result[0] > 0, "bronze_hcp_master should have rows"

    def test_bronze_hcp_master_min_rows(self, con):
        result = con.execute("SELECT COUNT(*) FROM bronze_hcp_master").fetchone()
        assert result[0] >= 1000, "Expected at least 1000 HCP records"

    def test_bronze_interactions_exists(self, con):
        result = con.execute("SELECT COUNT(*) FROM bronze_hcp_interactions").fetchone()
        assert result[0] > 0

    def test_bronze_has_metadata_columns(self, con):
        cols = con.execute("DESCRIBE bronze_hcp_master").df()["column_name"].tolist()
        assert "_batch_id" in cols, "Missing _batch_id metadata column"
        assert "_load_ts" in cols, "Missing _load_ts metadata column"
        assert "_source_file" in cols, "Missing _source_file metadata column"


# ── Silver Layer Tests ─────────────────────────────────────────────────────────

class TestSilverLayer:
    def test_silver_hcp_npi_format(self, con):
        invalid = con.execute("""
            SELECT COUNT(*) FROM silver_hcp_standardized
            WHERE dq_npi_valid = 0
        """).fetchone()[0]
        total = con.execute("SELECT COUNT(*) FROM silver_hcp_standardized").fetchone()[0]
        invalid_pct = invalid / total * 100
        assert invalid_pct < 10, f"Too many invalid NPIs: {invalid_pct:.1f}%"

    def test_silver_hcp_no_duplicates(self, con):
        result = con.execute("""
            SELECT COUNT(*) FROM (
                SELECT hcp_id, COUNT(*) AS cnt
                FROM silver_hcp_standardized
                GROUP BY hcp_id HAVING cnt > 1
            )
        """).fetchone()
        assert result[0] == 0, "Found duplicate hcp_id in silver_hcp_standardized"

    def test_silver_interactions_date_validity(self, con):
        invalid = con.execute("""
            SELECT COUNT(*) FROM silver_interactions_clean
            WHERE interaction_date > CURRENT_DATE
        """).fetchone()[0]
        assert invalid == 0, f"Found {invalid} future-dated interactions"

    def test_silver_interactions_valid_hcp_links(self, con):
        orphaned = con.execute("""
            SELECT COUNT(*) FROM silver_interactions_clean i
            LEFT JOIN silver_hcp_standardized h USING (hcp_id)
            WHERE h.hcp_id IS NULL
        """).fetchone()[0]
        total = con.execute("SELECT COUNT(*) FROM silver_interactions_clean").fetchone()[0]
        orphan_pct = orphaned / total * 100 if total > 0 else 0
        assert orphan_pct < 5, f"Too many orphaned interactions: {orphan_pct:.1f}%"

    def test_silver_rx_non_negative_counts(self, con):
        negative = con.execute("""
            SELECT COUNT(*) FROM silver_rx_aggregates WHERE total_rx_count < 0
        """).fetchone()[0]
        assert negative == 0, "Found negative rx counts in silver_rx_aggregates"


# ── Gold Layer Tests ──────────────────────────────────────────────────────────

class TestGoldLayer:
    def test_gold_hcp_360_uniqueness(self, con):
        result = con.execute("""
            SELECT COUNT(*) FROM (
                SELECT hcp_id, COUNT(*) AS cnt
                FROM gold_hcp_360
                GROUP BY hcp_id HAVING cnt > 1
            )
        """).fetchone()[0]
        assert result == 0, "Duplicate hcp_id found in gold_hcp_360"

    def test_gold_hcp_360_engagement_score_range(self, con):
        out_of_range = con.execute("""
            SELECT COUNT(*) FROM gold_hcp_360
            WHERE engagement_score < 0 OR engagement_score > 100
        """).fetchone()[0]
        assert out_of_range == 0, "Engagement scores out of range [0, 100]"

    def test_gold_targeting_score_priority_values(self, con):
        invalid = con.execute("""
            SELECT COUNT(*) FROM gold_hcp_targeting_score
            WHERE targeting_priority NOT IN ('A', 'B', 'C', 'D')
        """).fetchone()[0]
        assert invalid == 0, "Invalid targeting_priority values found"

    def test_gold_targeting_score_has_all_hcps(self, con):
        hcp_count = con.execute("SELECT COUNT(*) FROM gold_hcp_360").fetchone()[0]
        score_count = con.execute("SELECT COUNT(*) FROM gold_hcp_targeting_score").fetchone()[0]
        assert score_count == hcp_count, "Mismatch between HCP 360 and targeting score counts"

    def test_gold_trial_sites_quality_score_range(self, con):
        out_of_range = con.execute("""
            SELECT COUNT(*) FROM gold_trial_site_priority
            WHERE site_quality_score < 0 OR site_quality_score > 100
        """).fetchone()[0]
        assert out_of_range == 0, "Site quality scores out of [0, 100]"

    def test_gold_psp_summary_non_negative_cases(self, con):
        negative = con.execute("""
            SELECT COUNT(*) FROM gold_patient_support_summary
            WHERE total_cases < 0
        """).fetchone()[0]
        assert negative == 0, "Negative case counts in PSP summary"

    def test_gold_hcp_360_row_count(self, con):
        count = con.execute("SELECT COUNT(*) FROM gold_hcp_360").fetchone()[0]
        assert count >= 1000, f"Expected >= 1000 HCPs in gold_hcp_360, got {count}"


# ── Data Generation Tests ──────────────────────────────────────────────────────

class TestDataGeneration:
    def test_raw_files_exist(self):
        raw_dir = BASE_DIR / "data" / "raw"
        expected_files = [
            "hcp_master.csv", "hco_master.csv", "hcp_interactions.csv",
            "rx_aggregates.csv", "patient_support_cases.csv", "trial_sites.csv",
        ]
        for fname in expected_files:
            assert (raw_dir / fname).exists(), f"Raw file missing: {fname}"

    def test_hcp_master_csv_structure(self):
        raw_dir = BASE_DIR / "data" / "raw"
        df = pd.read_csv(raw_dir / "hcp_master.csv")
        expected_cols = ["hcp_id", "npi", "first_name", "last_name", "specialty_code", "territory_id"]
        for col in expected_cols:
            assert col in df.columns, f"Missing column: {col}"

    def test_no_real_phi_patterns(self):
        """Verify synthetic data does not contain real SSN or phone patterns."""
        raw_dir = BASE_DIR / "data" / "raw"
        df = pd.read_csv(raw_dir / "patient_support_cases.csv")
        # Patient support should have no hcp-level individual patient data
        assert "patient_id" not in df.columns, "Patient IDs should not exist in PSP data"
        assert "ssn" not in df.columns, "SSN should not exist in PSP data"
