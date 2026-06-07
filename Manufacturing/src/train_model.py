"""
Manufacturing Failure Prediction Model
Trains a Random Forest classifier to predict equipment failure in the next 7 days.
Features include rolling sensor statistics, asset attributes, and maintenance history.
"""

import json
import joblib
import duckdb
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    classification_report, roc_auc_score, average_precision_score, confusion_matrix
)

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "manufacturing.duckdb"
MODELS_DIR = BASE_DIR / "models"
OUTPUTS_DIR = BASE_DIR / "outputs"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLS = [
    "avg_temp", "avg_vibration", "avg_pressure", "avg_speed",
    "max_temp", "max_vibration",
    "std_temp", "std_vibration",
    "total_anomalies_day", "total_outliers_day",
    "sensor_completeness_pct",
    "age_years", "criticality_num", "maintenance_interval_days",
    "days_since_last_maintenance", "failures_last_90d",
]
TARGET_COL = "failure_in_next_7d"


def load_features(con):
    cols = ", ".join(FEATURE_COLS + [TARGET_COL])
    df = con.execute(f"""
        SELECT {cols}
        FROM gold_failure_prediction_features
        WHERE failure_in_next_7d IS NOT NULL
    """).df()
    df[FEATURE_COLS] = df[FEATURE_COLS].fillna(df[FEATURE_COLS].median())
    return df


def train(df):
    X = df[FEATURE_COLS]
    y = df[TARGET_COL].astype(int)

    print(f"Training data: {len(df):,} asset-day records")
    print(f"Failure rate: {y.mean()*100:.2f}%")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    auc_roc = roc_auc_score(y_test, y_proba)

    print(f"\nAUC-ROC: {auc_roc:.4f}")
    print(classification_report(y_test, y_pred, target_names=["No Failure", "Failure"]))

    fi = pd.DataFrame({
        "feature": FEATURE_COLS,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)

    print("\nTop Feature Importances:")
    print(fi.head(8).to_string(index=False))

    return model, X_test, y_test, y_proba, auc_roc, fi


def save_artifacts(model, fi, auc_roc):
    joblib.dump(model, MODELS_DIR / "failure_prediction_model.joblib")

    metadata = {
        "model_name": "Equipment Failure Prediction Model",
        "model_type": "RandomForestClassifier",
        "trained_at": datetime.now().isoformat(),
        "target": "failure_in_next_7d",
        "prediction_horizon": "7 days",
        "features": FEATURE_COLS,
        "auc_roc": round(auc_roc, 4),
        "feature_importances": fi.to_dict("records"),
        "model_card": {
            "intended_use": "Predict equipment failure risk within 7 days for maintenance prioritization",
            "limitations": "Trained on synthetic data. Sensor drift patterns are simulated.",
            "training_data": "gold_failure_prediction_features",
            "critical_data_dependencies": [
                "Sensor completeness >= 80% required for reliable predictions",
                "Timestamp quality must be validated before features are computed",
                "Rolling windows require gap-free sensor data or explicit imputation",
            ],
            "explainability": "Feature importances provided. SHAP values available per prediction.",
        }
    }

    with open(OUTPUTS_DIR / "model_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    print(f"\nModel artifacts saved to: {MODELS_DIR}")


def main():
    print("Training Manufacturing Failure Prediction Model...")
    con = duckdb.connect(str(DB_PATH))
    try:
        df = load_features(con)
        model, X_test, y_test, y_proba, auc_roc, fi = train(df)
        save_artifacts(model, fi, auc_roc)
    finally:
        con.close()


if __name__ == "__main__":
    main()
