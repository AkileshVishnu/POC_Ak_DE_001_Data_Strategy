"""Manufacturing Model Evaluation."""

import json
import joblib
import duckdb
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from sklearn.metrics import (
    accuracy_score, roc_auc_score, average_precision_score,
    confusion_matrix, precision_score, recall_score, f1_score
)
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "manufacturing.duckdb"
MODELS_DIR = BASE_DIR / "models"
OUTPUTS_DIR = BASE_DIR / "outputs"

FEATURE_COLS = [
    "avg_temp", "avg_vibration", "avg_pressure", "avg_speed",
    "max_temp", "max_vibration", "std_temp", "std_vibration",
    "total_anomalies_day", "total_outliers_day", "sensor_completeness_pct",
    "age_years", "criticality_num", "maintenance_interval_days",
    "days_since_last_maintenance", "failures_last_90d",
]


def main():
    print("Evaluating Manufacturing Failure Prediction Model...")
    con = duckdb.connect(str(DB_PATH))
    model = joblib.load(MODELS_DIR / "failure_prediction_model.joblib")

    df = con.execute(f"""
        SELECT {', '.join(FEATURE_COLS)}, failure_in_next_7d
        FROM gold_failure_prediction_features
        WHERE failure_in_next_7d IS NOT NULL
    """).df()

    df[FEATURE_COLS] = df[FEATURE_COLS].fillna(df[FEATURE_COLS].median())
    X = df[FEATURE_COLS]
    y = df["failure_in_next_7d"].astype(int)

    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    fi = sorted(
        [{"feature": f, "importance": round(float(i), 4)}
         for f, i in zip(FEATURE_COLS, model.feature_importances_)],
        key=lambda x: x["importance"], reverse=True
    )

    report = {
        "evaluation_timestamp": datetime.now().isoformat(),
        "test_set_size": len(X_test),
        "failure_count_in_test": int(y_test.sum()),
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "auc_roc": round(roc_auc_score(y_test, y_proba), 4),
        "auc_pr": round(average_precision_score(y_test, y_proba), 4),
        "precision_failure": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall_failure": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1_failure": round(f1_score(y_test, y_pred, zero_division=0), 4),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "top_5_features": fi[:5],
        "data_quality_note": (
            "All rolling sensor features are computed on validated data with timestamp "
            "and range checks applied. Sensor completeness is tracked per prediction."
        ),
    }

    print("\n" + "=" * 65)
    print("  MANUFACTURING FAILURE PREDICTION EVALUATION REPORT")
    print("=" * 65)
    print(f"  Test Set Size:       {report['test_set_size']:,}")
    print(f"  Failures in Test:    {report['failure_count_in_test']:,}")
    print(f"  AUC-ROC:             {report['auc_roc']:.4f}")
    print(f"  Precision (Failure): {report['precision_failure']:.4f}")
    print(f"  Recall (Failure):    {report['recall_failure']:.4f}")
    print(f"  F1 (Failure):        {report['f1_failure']:.4f}")
    print("\n  Top Features:")
    for feat in report["top_5_features"]:
        bar = "█" * int(feat["importance"] * 60)
        print(f"    {feat['feature']:<40} {bar} {feat['importance']:.4f}")
    print("=" * 65)

    with open(OUTPUTS_DIR / "model_evaluation.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nEvaluation saved to: {OUTPUTS_DIR / 'model_evaluation.json'}")
    con.close()


if __name__ == "__main__":
    main()
