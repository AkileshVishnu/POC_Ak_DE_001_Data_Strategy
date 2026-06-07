"""
Healthcare Model Evaluation
Loads trained model and generates evaluation report with metrics, confusion matrix,
and top feature drivers for explainability.
"""

import json
import joblib
import duckdb
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    confusion_matrix, classification_report
)
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "healthcare.duckdb"
MODELS_DIR = BASE_DIR / "models"
OUTPUTS_DIR = BASE_DIR / "outputs"

FEATURE_COLS = [
    "total_interactions_12m", "interactions_90d", "days_since_last_interaction",
    "positive_outcomes", "total_rx_12m", "total_new_starts_12m",
    "market_share_pct", "total_psp_cases", "engagement_score",
    "is_kol_flag", "is_investigator_flag", "years_in_practice", "specialty_tier_num",
]
SPECIALTY_TIER_MAP = {"A": 4, "B": 3, "C": 2, "D": 1}


def load_artifacts():
    model = joblib.load(MODELS_DIR / "hcp_targeting_model.joblib")
    le = joblib.load(MODELS_DIR / "hcp_targeting_label_encoder.joblib")
    return model, le


def load_data(con):
    df = con.execute("""
        SELECT *,
               CASE specialty_tier WHEN 'A' THEN 4 WHEN 'B' THEN 3 WHEN 'C' THEN 2 ELSE 1 END AS specialty_tier_num
        FROM gold_hcp_targeting_score
        WHERE targeting_priority IS NOT NULL
    """).df()
    df[FEATURE_COLS] = df[FEATURE_COLS].fillna(0)
    return df


def evaluate(model, le, df):
    X = df[FEATURE_COLS]
    y_true_enc = le.transform(df["targeting_priority"])
    _, X_test, _, y_test = train_test_split(X, y_true_enc, test_size=0.2, random_state=42, stratify=y_true_enc)

    y_pred = model.predict(X_test)

    report = {
        "evaluation_timestamp": datetime.now().isoformat(),
        "test_set_size": len(X_test),
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "f1_macro": round(f1_score(y_test, y_pred, average="macro"), 4),
        "precision_macro": round(precision_score(y_test, y_pred, average="macro"), 4),
        "recall_macro": round(recall_score(y_test, y_pred, average="macro"), 4),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "target_classes": le.classes_.tolist(),
        "per_class_report": classification_report(
            y_test, y_pred, target_names=le.classes_, output_dict=True
        ),
        "top_features": sorted(
            [{"feature": f, "importance": round(float(i), 4)}
             for f, i in zip(FEATURE_COLS, model.feature_importances_)],
            key=lambda x: x["importance"], reverse=True
        )[:5],
    }

    return report


def print_evaluation(report):
    print("\n" + "=" * 60)
    print("  HEALTHCARE MODEL EVALUATION REPORT")
    print("=" * 60)
    print(f"  Test Set Size:    {report['test_set_size']:,}")
    print(f"  Accuracy:         {report['accuracy']:.4f}")
    print(f"  F1 (Macro):       {report['f1_macro']:.4f}")
    print(f"  Precision (Mac):  {report['precision_macro']:.4f}")
    print(f"  Recall (Mac):     {report['recall_macro']:.4f}")
    print("\n  Top 5 Predictive Features:")
    for feat in report["top_features"]:
        bar = "█" * int(feat["importance"] * 50)
        print(f"    {feat['feature']:<40} {bar} {feat['importance']:.4f}")
    print("=" * 60)


def main():
    print("Evaluating Healthcare HCP Targeting Model...")
    con = duckdb.connect(str(DB_PATH))
    try:
        model, le = load_artifacts()
        df = load_data(con)
        report = evaluate(model, le, df)
        print_evaluation(report)

        output_path = OUTPUTS_DIR / "model_evaluation.json"
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nEvaluation report saved to: {output_path}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
