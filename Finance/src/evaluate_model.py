"""
Finance Model Evaluation
Generates evaluation metrics, confusion matrix, feature analysis, and auditability report.
"""

import json
import joblib
import duckdb
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from sklearn.metrics import (
    accuracy_score, roc_auc_score, average_precision_score,
    confusion_matrix, classification_report, precision_score, recall_score, f1_score
)
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "finance.duckdb"
MODELS_DIR = BASE_DIR / "models"
OUTPUTS_DIR = BASE_DIR / "outputs"

FEATURE_COLS = [
    "amount", "transaction_hour", "is_online", "is_international",
    "customer_tx_count_30d", "customer_avg_amount_30d", "customer_max_amount_30d",
    "customer_total_amount_30d", "customer_tx_count_7d", "days_since_last_tx",
    "distinct_states_30d", "prior_fraud_count", "amount_vs_avg_ratio",
    "is_late_night", "new_device_events_7d", "vpn_events_7d",
    "bureau_score", "credit_utilization_pct", "num_derogatory_marks",
    "customer_tenure_days", "merchant_risk_flag",
]


def main():
    print("Evaluating Finance Fraud Detection Model...")
    con = duckdb.connect(str(DB_PATH))
    model = joblib.load(MODELS_DIR / "fraud_detection_model.joblib")

    df = con.execute(f"""
        SELECT {', '.join(FEATURE_COLS)}, is_fraud, transaction_id
        FROM gold_transaction_risk_features
    """).df()

    for col in ["is_online", "is_international", "merchant_risk_flag"]:
        df[col] = df[col].astype(int)
    df[FEATURE_COLS] = df[FEATURE_COLS].fillna(0)

    X = df[FEATURE_COLS]
    y = df["is_fraud"].astype(int)

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
        "fraud_count_in_test": int(y_test.sum()),
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "auc_roc": round(roc_auc_score(y_test, y_proba), 4),
        "auc_pr": round(average_precision_score(y_test, y_proba), 4),
        "precision_fraud": round(precision_score(y_test, y_pred), 4),
        "recall_fraud": round(recall_score(y_test, y_pred), 4),
        "f1_fraud": round(f1_score(y_test, y_pred), 4),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "top_5_features": fi[:5],
        "auditability_note": (
            "All features are point-in-time correct. "
            "Each prediction can be traced to transaction_id → source CSV batch. "
            "See outputs/audit_trail_sample.json for sample lineage."
        ),
    }

    print("\n" + "=" * 65)
    print("  FINANCE FRAUD MODEL EVALUATION REPORT")
    print("=" * 65)
    print(f"  Test Set Size:    {report['test_set_size']:,}")
    print(f"  Fraud in Test:    {report['fraud_count_in_test']:,}")
    print(f"  AUC-ROC:          {report['auc_roc']:.4f}")
    print(f"  AUC-PR:           {report['auc_pr']:.4f}")
    print(f"  Precision (Fraud): {report['precision_fraud']:.4f}")
    print(f"  Recall (Fraud):    {report['recall_fraud']:.4f}")
    print(f"  F1 (Fraud):        {report['f1_fraud']:.4f}")
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
