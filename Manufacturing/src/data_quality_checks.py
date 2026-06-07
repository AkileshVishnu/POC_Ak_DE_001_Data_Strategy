"""
Manufacturing Data Quality Checks
Validates timestamp quality, sensor range, gap detection, and feature completeness.
"""

import json
import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "manufacturing.duckdb"
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

    # Timestamp quality
    checks.append(run_check(con, "sensor_timestamp_not_future_pct",
        "SELECT AVG(dq_timestamp_not_future) * 100 FROM silver_sensors_clean",
        threshold=99.0))

    checks.append(run_check(con, "sensor_timestamp_not_ancient_pct",
        "SELECT AVG(dq_timestamp_not_ancient) * 100 FROM silver_sensors_clean",
        threshold=99.0))

    # Sensor range validation
    checks.append(run_check(con, "sensor_value_in_range_pct",
        "SELECT AVG(dq_value_in_range) * 100 FROM silver_sensors_clean",
        threshold=95.0))

    checks.append(run_check(con, "sensor_hard_outlier_rate_pct",
        "SELECT AVG(is_hard_outlier) * 100 FROM silver_sensors_clean",
        threshold=2.0, higher_is_better=False))

    checks.append(run_check(con, "sensor_anomaly_rate_pct",
        "SELECT AVG(is_anomaly) * 100 FROM silver_sensors_clean",
        threshold=20.0, higher_is_better=False))

    # Gap detection (check that sensor quality scores capture gap info)
    checks.append(run_check(con, "gold_sensor_quality_score_coverage",
        "SELECT COUNT(*) FROM gold_sensor_quality_score", threshold=50))

    checks.append(run_check(con, "gold_sensor_min_quality_score_avg",
        "SELECT AVG(sensor_quality_score) FROM gold_sensor_quality_score", threshold=60.0))

    # Asset data product completeness
    checks.append(run_check(con, "gold_asset_health_all_assets",
        "SELECT COUNT(*) FROM gold_asset_health_summary", threshold=50))

    checks.append(run_check(con, "gold_asset_health_score_range",
        """SELECT COUNT(*) FROM gold_asset_health_summary
           WHERE asset_health_score < 0 OR asset_health_score > 100""",
        threshold=0, higher_is_better=False))

    checks.append(run_check(con, "gold_features_failure_label_coverage",
        """SELECT COUNT(CASE WHEN failure_in_next_7d IS NOT NULL THEN 1 END)::DOUBLE /
                  COUNT(*) * 100
           FROM gold_failure_prediction_features""",
        threshold=99.0))

    # Rolling features not null
    checks.append(run_check(con, "gold_features_avg_temp_completeness",
        """SELECT COUNT(CASE WHEN avg_temp IS NOT NULL THEN 1 END)::DOUBLE /
                  COUNT(*) * 100
           FROM gold_failure_prediction_features""",
        threshold=70.0))  # some assets may not have all sensors

    checks.append(run_check(con, "gold_maintenance_recommendations_coverage",
        "SELECT COUNT(*) FROM gold_maintenance_recommendations", threshold=50))

    # Feature freshness
    checks.append(run_check(con, "gold_features_recent_feature_ts",
        """SELECT COUNT(*) FROM gold_failure_prediction_features
           WHERE feature_ts < CURRENT_TIMESTAMP - INTERVAL '24 hours'""",
        threshold=0, higher_is_better=False))

    return checks


def generate_report(checks):
    total = len(checks)
    passed = sum(1 for c in checks if c["passed"])
    overall_score = round(passed / total * 100, 1) if total > 0 else 0
    return {
        "report_generated_at": datetime.now().isoformat(),
        "project": "Manufacturing",
        "overall_score": overall_score,
        "total_checks": total,
        "passed_checks": passed,
        "failed_checks": total - passed,
        "status": "HEALTHY" if overall_score >= 85 else "DEGRADED" if overall_score >= 60 else "CRITICAL",
        "checks": checks,
        "failed_check_names": [c["check_name"] for c in checks if not c["passed"]],
    }


def print_report(report):
    print("\n" + "=" * 70)
    print("  MANUFACTURING TIME-SERIES DATA QUALITY REPORT")
    print("=" * 70)
    print(f"  Overall Score:  {report['overall_score']}%  [{report['status']}]")
    print(f"  Passed: {report['passed_checks']} / {report['total_checks']}")
    print("-" * 70)
    for c in report["checks"]:
        icon = "✓" if c["passed"] else "✗"
        val = f"{c['value']}" if c["value"] is not None else "ERROR"
        print(f"  {icon} {c['check_name']:<50} {val}")
    print("=" * 70)


def main():
    print("Running Manufacturing time-series data quality checks...")
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
