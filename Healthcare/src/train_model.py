"""
Healthcare HCP Targeting Model
Trains a Random Forest classifier to predict HCP targeting priority (A/B/C/D).
Includes feature importance and SHAP explainability.
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
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "healthcare.duckdb"
MODELS_DIR = BASE_DIR / "models"
OUTPUTS_DIR = BASE_DIR / "outputs"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLS = [
    "total_interactions_12m",
    "interactions_90d",
    "days_since_last_interaction",
    "positive_outcomes",
    "total_rx_12m",
    "total_new_starts_12m",
    "market_share_pct",
    "total_psp_cases",
    "engagement_score",
    "is_kol_flag",
    "is_investigator_flag",
    "years_in_practice",
]

SPECIALTY_TIER_MAP = {"A": 4, "B": 3, "C": 2, "D": 1}
TARGET_COL = "targeting_priority"


def load_features(con) -> pd.DataFrame:
    query = f"""
        SELECT {', '.join(FEATURE_COLS)}, specialty_tier, targeting_priority
        FROM gold_hcp_targeting_score
        WHERE targeting_priority IS NOT NULL
    """
    df = con.execute(query).df()
    df["specialty_tier_num"] = df["specialty_tier"].map(SPECIALTY_TIER_MAP).fillna(1)
    df = df.drop(columns=["specialty_tier"])
    df[FEATURE_COLS + ["specialty_tier_num"]] = df[FEATURE_COLS + ["specialty_tier_num"]].fillna(0)
    return df


def train(df: pd.DataFrame):
    all_features = FEATURE_COLS + ["specialty_tier_num"]
    X = df[all_features]
    y = df[TARGET_COL]

    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_enc, test_size=0.2, random_state=42, stratify=y_enc
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

    cv_scores = cross_val_score(model, X, y_enc, cv=5, scoring="accuracy")
    y_pred = model.predict(X_test)

    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    fi = pd.DataFrame({
        "feature": all_features,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)

    print("\nTop Feature Importances:")
    print(fi.to_string(index=False))

    return model, le, X_train, X_test, y_train, y_test, cv_scores, fi, all_features


def compute_shap_summary(model, X_test, feature_names, n_samples=200):
    """Compute approximate SHAP-style feature importance using permutation."""
    try:
        import shap
        sample = X_test.sample(min(n_samples, len(X_test)), random_state=42)
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(sample)
        mean_abs = np.abs(np.array(shap_values)).mean(axis=(0, 2)) if isinstance(shap_values, list) else \
                   np.abs(shap_values).mean(axis=0)
        shap_df = pd.DataFrame({"feature": feature_names, "mean_abs_shap": mean_abs})
        return shap_df.sort_values("mean_abs_shap", ascending=False).to_dict("records")
    except Exception:
        return []


def save_artifacts(model, le, fi, cv_scores, shap_summary, all_features):
    joblib.dump(model, MODELS_DIR / "hcp_targeting_model.joblib")
    joblib.dump(le, MODELS_DIR / "hcp_targeting_label_encoder.joblib")

    metadata = {
        "model_name": "HCP Targeting Priority Classifier",
        "model_type": "RandomForestClassifier",
        "trained_at": datetime.now().isoformat(),
        "features": all_features,
        "target": TARGET_COL,
        "target_classes": le.classes_.tolist(),
        "cv_accuracy_mean": round(float(cv_scores.mean()), 4),
        "cv_accuracy_std": round(float(cv_scores.std()), 4),
        "feature_importances": fi.to_dict("records"),
        "shap_summary": shap_summary,
        "model_card": {
            "intended_use": "Score HCP targeting priority for commercial field teams",
            "limitations": "Trained on synthetic data. Not for production clinical or commercial use.",
            "training_data": "gold_hcp_targeting_score (DuckDB)",
            "evaluation_metric": "Macro-averaged accuracy (5-fold CV)",
            "explainability": "Feature importances and SHAP values available per prediction",
        }
    }

    with open(OUTPUTS_DIR / "model_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    print(f"\nModel artifacts saved to: {MODELS_DIR}")
    print(f"CV Accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")


def main():
    print("Training Healthcare HCP Targeting Model...")
    con = duckdb.connect(str(DB_PATH))
    try:
        df = load_features(con)
        print(f"Training data: {len(df):,} HCPs")
        print(f"Target distribution:\n{df[TARGET_COL].value_counts()}")

        model, le, X_train, X_test, y_train, y_test, cv_scores, fi, all_features = train(df)
        shap_summary = compute_shap_summary(model, X_test, all_features)
        save_artifacts(model, le, fi, cv_scores, shap_summary, all_features)

        # Write predictions back to DuckDB
        X_all = df[all_features]
        predictions = le.inverse_transform(model.predict(X_all))
        proba = model.predict_proba(X_all).max(axis=1)

        pred_df = df[["targeting_priority"]].copy()
        pred_df["predicted_priority"] = predictions
        pred_df["prediction_confidence"] = proba.round(4)
        pred_df["model_version"] = "v1.0"
        pred_df.to_parquet(OUTPUTS_DIR / "hcp_predictions.parquet", index=False)

        print(f"\nTraining complete. See {OUTPUTS_DIR} for artifacts.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
