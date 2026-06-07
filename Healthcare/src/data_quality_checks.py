"""
Healthcare Data Quality Checks
Validates data across Bronze, Silver, and Gold layers.
Outputs a quality scorecard to outputs/quality_report.json
"""

import json
import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "healthcare.duckdb"
OUTPUTS_DIR = BASE_DIR / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def get_connection():
    return duckdb.connect(str(DB_PATH))


def run_check(con, name: str, query: str, threshold: float, higher_is_better: bool = True) -> dict:
    """Run a single DQ check and return result dict."""
    try:
        result = con.execute(query).fetchone()
        value = float(result[0]) if result and result[0] is not None else 0.0
        if higher_is_better:
            passed = value >= threshold
        else:
            passed = value <= threshold
        return {
            "check_name": name,
            "value": round(value, 4),
            "threshold": threshold,
            "passed": passed,
            "status": "PASS" if passed else "FAIL",
        }
    except Exception as e:
        return {
            "check_name": name,
            "value": None,
            "threshold": threshold,
            "passed": False,
            "status": "ERROR",
            "error": str(e),
        }


def run_all_checks(con) -> list:
    checks = []

    # ── Bronze Layer Checks ────────────────────────────────────────────────────
    checks.append(run_check(con,
        "bronze_hcp_master_row_count",
        "SELECT COUNT(*) FROM bronze_hcp_master",
        threshold=1000))

    checks.append(run_check(con,
        "bronze_interactions_row_count",
        "SELECT COUNT(*) FROM bronze_hcp_interactions",
        threshold=10000))

    # ── Silver Layer Checks ────────────────────────────────────────────────────
    checks.append(run_check(con,
        "silver_hcp_npi_completeness_pct",
        "SELECT AVG(dq_npi_valid) * 100 FROM silver_hcp_standardized",
        threshold=95.0))

    checks.append(run_check(con,
        "silver_hcp_name_completeness_pct",
        "SELECT AVG(dq_name_complete) * 100 FROM silver_hcp_standardized",
        threshold=99.0))

    checks.append(run_check(con,
        "silver_hcp_specialty_completeness_pct",
        "SELECT AVG(dq_specialty_present) * 100 FROM silver_hcp_standardized",
        threshold=98.0))

    checks.append(run_check(con,
        "silver_hcp_uniqueness_pct",
        """
        SELECT (COUNT(*) - COUNT(DISTINCT hcp_id))::DOUBLE / COUNT(*) * 100
        FROM silver_hcp_standardized
        """,
        threshold=0.0,
        higher_is_better=False))

    checks.append(run_check(con,
        "silver_interactions_valid_date_pct",
        "SELECT AVG(dq_date_valid) * 100 FROM silver_interactions_clean",
        threshold=99.0))

    checks.append(run_check(con,
        "silver_interactions_hcp_linkage_pct",
        """
        SELECT COUNT(CASE WHEN h.hcp_id IS NOT NULL THEN 1 END)::DOUBLE /
               COUNT(*) * 100
        FROM silver_interactions_clean i
        LEFT JOIN silver_hcp_standardized h USING (hcp_id)
        """,
        threshold=95.0))

    # ── Gold Layer Checks ──────────────────────────────────────────────────────
    checks.append(run_check(con,
        "gold_hcp_360_uniqueness",
        """
        SELECT (COUNT(*) - COUNT(DISTINCT hcp_id))::DOUBLE / COUNT(*) * 100
        FROM gold_hcp_360
        """,
        threshold=0.0,
        higher_is_better=False))

    checks.append(run_check(con,
        "gold_hcp_360_engagement_score_range",
        """
        SELECT COUNT(CASE WHEN engagement_score < 0 OR engagement_score > 100 THEN 1 END)::DOUBLE /
               COUNT(*) * 100
        FROM gold_hcp_360
        """,
        threshold=0.0,
        higher_is_better=False))

    checks.append(run_check(con,
        "gold_targeting_score_priority_coverage",
        """
        SELECT COUNT(CASE WHEN targeting_priority IS NOT NULL THEN 1 END)::DOUBLE /
               COUNT(*) * 100
        FROM gold_hcp_targeting_score
        """,
        threshold=100.0))

    checks.append(run_check(con,
        "gold_targeting_tier_distribution_a_pct",
        """
        SELECT COUNT(CASE WHEN targeting_priority = 'A' THEN 1 END)::DOUBLE /
               COUNT(*) * 100
        FROM gold_hcp_targeting_score
        """,
        threshold=5.0))

    checks.append(run_check(con,
        "gold_trial_site_priority_completeness",
        """
        SELECT COUNT(CASE WHEN site_quality_score IS NOT NULL THEN 1 END)::DOUBLE /
               COUNT(*) * 100
        FROM gold_trial_site_priority
        """,
        threshold=98.0))

    checks.append(run_check(con,
        "gold_psp_summary_territory_coverage",
        """
        SELECT COUNT(DISTINCT territory_id)
        FROM gold_patient_support_summary
        """,
        threshold=20))

    return checks


def generate_report(checks: list) -> dict:
    total = len(checks)
    passed = sum(1 for c in checks if c["passed"])
    failed = [c for c in checks if not c["passed"]]
    overall_score = round(passed / total * 100, 1) if total > 0 else 0

    report = {
        "report_generated_at": datetime.now().isoformat(),
        "project": "Healthcare",
        "overall_score": overall_score,
        "total_checks": total,
        "passed_checks": passed,
        "failed_checks": total - passed,
        "status": "HEALTHY" if overall_score >= 85 else "DEGRADED" if overall_score >= 60 else "CRITICAL",
        "checks": checks,
        "failed_check_names": [c["check_name"] for c in failed],
    }
    return report


def print_report(report: dict):
    print("\n" + "=" * 60)
    print("  HEALTHCARE DATA QUALITY REPORT")
    print("=" * 60)
    print(f"  Overall Score:  {report['overall_score']}%  [{report['status']}]")
    print(f"  Passed: {report['passed_checks']} / {report['total_checks']}")
    print("-" * 60)
    for c in report["checks"]:
        icon = "✓" if c["passed"] else "✗"
        val = f"{c['value']}" if c["value"] is not None else "ERROR"
        print(f"  {icon} {c['check_name']:<45} {val}")
    print("=" * 60)
    if report["failed_check_names"]:
        print("  FAILED CHECKS:")
        for name in report["failed_check_names"]:
            print(f"    - {name}")
    print()


def main():
    print("Running Healthcare data quality checks...")
    con = get_connection()
    try:
        checks = run_all_checks(con)
        report = generate_report(checks)
        print_report(report)

        output_path = OUTPUTS_DIR / "quality_report.json"
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"Quality report saved to: {output_path}")

        if report["status"] == "CRITICAL":
            print("WARNING: Data quality is CRITICAL. Review failed checks before proceeding to model training.")

    finally:
        con.close()


if __name__ == "__main__":
    main()
