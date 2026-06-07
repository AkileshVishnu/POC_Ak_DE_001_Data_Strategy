"""
Finance Data Quality Checks
Validates feature freshness, completeness, and temporal integrity.
Generates outputs/quality_report.json
"""

import json
import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "finance.duckdb"
OUTPUTS_DIR = BASE_DIR / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def get_connection():
    return duckdb.connect(str(DB_PATH))


def run_check(con, name, query, threshold, higher_is_better=True):
    try:
        result = con.execute(query).fetchone()
        value = float(result[0]) if result and result[0] is not None else 0.0
        passed = value >= threshold if higher_is_better else value <= threshold
        return {"check_name": name, "value": round(value, 4), "threshold": threshold,
                "passed": passed, "status": "PASS" if passed else "FAIL"}
    except Exception as e:
        return {"check_name": name, "value": None, "threshold": threshold,
                "passed": False, "status": "ERROR", "error": str(e)}


def run_all_checks(con):
    checks = []

    # Bronze counts
    checks.append(run_check(con, "bronze_transactions_row_count",
        "SELECT COUNT(*) FROM bronze_transactions", threshold=50000))
    checks.append(run_check(con, "bronze_customers_row_count",
        "SELECT COUNT(*) FROM bronze_customers", threshold=1000))

    # Silver quality
    checks.append(run_check(con, "silver_transactions_amount_positive_pct",
        "SELECT AVG(dq_amount_positive) * 100 FROM silver_transactions_clean", threshold=99.0))
    checks.append(run_check(con, "silver_transactions_date_valid_pct",
        "SELECT AVG(dq_date_valid) * 100 FROM silver_transactions_clean", threshold=99.9))
    checks.append(run_check(con, "silver_transactions_no_future_dates",
        """SELECT COUNT(*) FROM silver_transactions_clean
           WHERE transaction_date > CURRENT_DATE""",
        threshold=0, higher_is_better=False))
    checks.append(run_check(con, "silver_customers_uniqueness",
        """SELECT (COUNT(*) - COUNT(DISTINCT customer_id))::DOUBLE / COUNT(*) * 100
           FROM silver_customers_clean""",
        threshold=0.0, higher_is_better=False))
    checks.append(run_check(con, "silver_transactions_customer_linkage_pct",
        """SELECT COUNT(CASE WHEN c.customer_id IS NOT NULL THEN 1 END)::DOUBLE /
                  COUNT(*) * 100
           FROM silver_transactions_clean t
           LEFT JOIN silver_customers_clean c USING (customer_id)""",
        threshold=98.0))

    # Gold feature quality
    checks.append(run_check(con, "gold_features_no_future_feature_ts",
        """SELECT COUNT(*) FROM gold_transaction_risk_features
           WHERE feature_ts > CURRENT_TIMESTAMP + INTERVAL '1 hour'""",
        threshold=0, higher_is_better=False))
    checks.append(run_check(con, "gold_features_bureau_score_range",
        """SELECT COUNT(*) FROM gold_transaction_risk_features
           WHERE bureau_score < 300 OR bureau_score > 850""",
        threshold=0, higher_is_better=False))
    checks.append(run_check(con, "gold_features_fraud_rate_realistic",
        """SELECT AVG(CAST(is_fraud AS DOUBLE)) * 100
           FROM gold_transaction_risk_features""",
        threshold=0.5))  # should have some fraud
    checks.append(run_check(con, "gold_customer_360_completeness",
        "SELECT COUNT(*) FROM gold_customer_360", threshold=4000))

    # Feature freshness check
    checks.append(run_check(con, "gold_features_feature_ts_recent",
        """SELECT COUNT(*) FROM gold_transaction_risk_features
           WHERE feature_ts < CURRENT_TIMESTAMP - INTERVAL '24 hours'""",
        threshold=0, higher_is_better=False))

    # Point-in-time integrity: features should not use future data
    checks.append(run_check(con, "gold_pit_no_negative_days_since_last",
        """SELECT COUNT(*) FROM gold_transaction_risk_features
           WHERE days_since_last_tx < 0""",
        threshold=0, higher_is_better=False))

    checks.append(run_check(con, "gold_risk_profile_tier_coverage",
        """SELECT COUNT(CASE WHEN risk_tier IS NOT NULL THEN 1 END)::DOUBLE /
                  COUNT(*) * 100
           FROM gold_customer_risk_profile""",
        threshold=100.0))

    return checks


def generate_report(checks):
    total = len(checks)
    passed = sum(1 for c in checks if c["passed"])
    overall_score = round(passed / total * 100, 1) if total > 0 else 0
    return {
        "report_generated_at": datetime.now().isoformat(),
        "project": "Finance",
        "overall_score": overall_score,
        "total_checks": total,
        "passed_checks": passed,
        "failed_checks": total - passed,
        "status": "HEALTHY" if overall_score >= 85 else "DEGRADED" if overall_score >= 60 else "CRITICAL",
        "checks": checks,
        "failed_check_names": [c["check_name"] for c in checks if not c["passed"]],
    }


def print_report(report):
    print("\n" + "=" * 65)
    print("  FINANCE DATA QUALITY & FEATURE INTEGRITY REPORT")
    print("=" * 65)
    print(f"  Overall Score:  {report['overall_score']}%  [{report['status']}]")
    print(f"  Passed: {report['passed_checks']} / {report['total_checks']}")
    print("-" * 65)
    for c in report["checks"]:
        icon = "✓" if c["passed"] else "✗"
        val = f"{c['value']}" if c["value"] is not None else "ERROR"
        print(f"  {icon} {c['check_name']:<50} {val}")
    print("=" * 65)


def main():
    print("Running Finance data quality and feature integrity checks...")
    con = get_connection()
    try:
        checks = run_all_checks(con)
        report = generate_report(checks)
        print_report(report)
        output_path = OUTPUTS_DIR / "quality_report.json"
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nQuality report saved to: {output_path}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
