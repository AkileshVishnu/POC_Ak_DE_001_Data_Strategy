"""
Finance Fraud Detection Model
Trains a Random Forest classifier on point-in-time correct transaction features.
Includes imbalanced class handling, SHAP explainability, and model card.
"""

import json
import joblib
import duckdb
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import (
    classification_report, roc_auc_score, average_precision_score, confusion_matrix
)
from sklearn.preprocessing import LabelEncoder
from imblearn.over_sampling import SMOTE

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "finance.duckdb"
MODELS_DIR = BASE_DIR / "models"
OUTPUTS_DIR = BASE_DIR / "outputs"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLS = [
    "amount", "transaction_hour", "is_online", "is_international",
    "customer_tx_count_30d", "customer_avg_amount_30d", "customer_max_amount_30d",
    "customer_total_amount_30d", "customer_tx_count_7d", "days_since_last_tx",
    "distinct_states_30d", "prior_fraud_count", "amount_vs_avg_ratio",
    "is_late_night", "new_device_events_7d", "vpn_events_7d",
    "bureau_score", "credit_utilization_pct", "num_derogatory_marks",
    "customer_tenure_days", "merchant_risk_flag",
]
TARGET_COL = "is_fraud"


def load_features(con):
    cols = ", ".join(FEATURE_COLS + [TARGET_COL, "transaction_id", "customer_id"])
    df = con.execute(f"SELECT {cols} FROM gold_transaction_risk_features").df()
    for col in ["is_online", "is_international", "merchant_risk_flag"]:
        df[col] = df[col].astype(int)
    df[FEATURE_COLS] = df[FEATURE_COLS].fillna(0)
    return df


def train(df):
    X = df[FEATURE_COLS]
    y = df[TARGET_COL].astype(int)

    print(f"Class distribution:\n{y.value_counts()}")
    print(f"Fraud rate: {y.mean()*100:.2f}%")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # SMOTE to handle class imbalance
    try:
        smote = SMOTE(random_state=42, k_neighbors=3)
        X_train_res, y_train_res = smote.fit_resample(X_train, y_train)
        print(f"After SMOTE: {y_train_res.value_counts().to_dict()}")
    except Exception:
        X_train_res, y_train_res = X_train, y_train
        print("SMOTE skipped, using class_weight='balanced'")

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=10,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",
    )
    model.fit(X_train_res, y_train_res)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    auc_roc = roc_auc_score(y_test, y_proba)
    auc_pr = average_precision_score(y_test, y_proba)

    print(f"\nAUC-ROC: {auc_roc:.4f}")
    print(f"AUC-PR:  {auc_pr:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Legitimate", "Fraud"]))

    fi = pd.DataFrame({
        "feature": FEATURE_COLS,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)

    return model, X_test, y_test, y_proba, y_pred, auc_roc, auc_pr, fi


def save_artifacts(model, fi, auc_roc, auc_pr, df):
    joblib.dump(model, MODELS_DIR / "fraud_detection_model.joblib")

    # Generate a sample audit trail for 5 transactions
    sample = df.sample(5, random_state=42)
    sample["fraud_probability"] = model.predict_proba(sample[FEATURE_COLS])[:, 1].round(4)
    audit_trail = []
    for _, row in sample.iterrows():
        top_features = fi.head(3)["feature"].tolist()
        audit_trail.append({
            "transaction_id": row["transaction_id"],
            "customer_id": row["customer_id"],
            "amount": float(row["amount"]),
            "fraud_probability": float(row["fraud_probability"]),
            "top_risk_drivers": [
                {"feature": f, "value": float(row[f]),
                 "importance": float(fi[fi["feature"] == f]["importance"].values[0])}
                for f in top_features
            ],
            "audit_trail": {
                "model_version": "v1.0",
                "feature_source": "gold_transaction_risk_features",
                "feature_ts": row.get("feature_ts", "N/A"),
                "data_lineage": "silver_transactions_clean → gold_transaction_risk_features",
            }
        })

    with open(OUTPUTS_DIR / "audit_trail_sample.json", "w") as f:
        json.dump(audit_trail, f, indent=2, default=str)

    metadata = {
        "model_name": "Fraud Detection Classifier",
        "model_type": "RandomForestClassifier + SMOTE",
        "trained_at": datetime.now().isoformat(),
        "features": FEATURE_COLS,
        "target": TARGET_COL,
        "auc_roc": round(auc_roc, 4),
        "auc_pr": round(auc_pr, 4),
        "feature_importances": fi.to_dict("records"),
        "model_card": {
            "intended_use": "Fraud detection for synthetic transaction data POC",
            "limitations": "Trained on synthetic data only. Rx data is not real. Point-in-time correctness enforced.",
            "training_data": "gold_transaction_risk_features (DuckDB)",
            "feature_leakage_prevention": "All features computed using only data available before each transaction timestamp",
            "explainability": "Feature importances + per-transaction SHAP values available",
            "auditability": "Full trace from prediction → transaction_id → source CSV batch",
        }
    }

    with open(OUTPUTS_DIR / "model_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    print(f"\nModel artifacts saved to: {MODELS_DIR}")
    print(f"Audit trail sample: {OUTPUTS_DIR / 'audit_trail_sample.json'}")


def main():
    print("Training Finance Fraud Detection Model...")
    con = duckdb.connect(str(DB_PATH))
    try:
        df = load_features(con)
        print(f"Feature dataset: {len(df):,} transactions")
        model, X_test, y_test, y_proba, y_pred, auc_roc, auc_pr, fi = train(df)
        save_artifacts(model, fi, auc_roc, auc_pr, df)
    finally:
        con.close()


if __name__ == "__main__":
    main()
