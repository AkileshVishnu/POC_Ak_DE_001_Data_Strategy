"""
Finance Fraud & Risk Dashboard
Streamlit dashboard for fraud monitoring, customer risk, feature quality, and audit.
"""

import json
import duckdb
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "finance.duckdb"
OUTPUTS_DIR = BASE_DIR / "outputs"

st.set_page_config(
    page_title="Finance Fraud & Risk Intelligence",
    page_icon="🏦",
    layout="wide",
)


@st.cache_data(ttl=300)
def load_transactions():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    return con.execute("SELECT * FROM gold_transaction_risk_features LIMIT 50000").df()


@st.cache_data(ttl=300)
def load_customers():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    return con.execute("SELECT * FROM gold_customer_360").df()


@st.cache_data(ttl=300)
def load_risk_profiles():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    return con.execute("SELECT * FROM gold_customer_risk_profile").df()


def load_quality_report():
    p = OUTPUTS_DIR / "quality_report.json"
    return json.load(open(p)) if p.exists() else None


def load_eval_report():
    p = OUTPUTS_DIR / "model_evaluation.json"
    return json.load(open(p)) if p.exists() else None


def load_audit_trail():
    p = OUTPUTS_DIR / "audit_trail_sample.json"
    return json.load(open(p)) if p.exists() else None


st.sidebar.title("🏦 Finance Risk Intelligence")
st.sidebar.markdown("Point-in-Time Feature Strategy")
page = st.sidebar.radio(
    "Navigate",
    ["Fraud Monitoring", "Customer Risk Profile", "Feature Quality Dashboard",
     "Audit Trail & Explainability", "Model Performance"]
)

if page == "Fraud Monitoring":
    st.title("Fraud Transaction Monitoring")
    try:
        df = load_transactions()
        fraud = df[df["is_fraud"] == True]
        legit = df[df["is_fraud"] == False]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Transactions", f"{len(df):,}")
        col2.metric("Fraud Transactions", f"{len(fraud):,}")
        col3.metric("Fraud Rate", f"{len(fraud)/len(df)*100:.2f}%")
        col4.metric("Avg Fraud Amount", f"${fraud['amount'].mean():.2f}")

        col_l, col_r = st.columns(2)
        with col_l:
            fig = px.histogram(df, x="amount", color="is_fraud",
                               barmode="overlay", nbins=50,
                               title="Transaction Amount Distribution",
                               color_discrete_map={True: "#ef4444", False: "#3b82f6"},
                               labels={"is_fraud": "Is Fraud"})
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            hour_fraud = df.groupby(["transaction_hour", "is_fraud"]).size().reset_index(name="count")
            fig = px.bar(hour_fraud, x="transaction_hour", y="count", color="is_fraud",
                         barmode="stack", title="Fraud by Hour of Day",
                         color_discrete_map={True: "#ef4444", False: "#3b82f6"})
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("High-Risk Transactions (fraud=True sample)")
        st.dataframe(fraud[["transaction_id", "customer_id", "amount", "transaction_hour",
                             "is_late_night", "is_international", "amount_vs_avg_ratio",
                             "distinct_states_30d"]].head(20), use_container_width=True)

    except Exception as e:
        st.error(f"Run the pipeline first: python src/run_pipeline.py\n\n{e}")

elif page == "Customer Risk Profile":
    st.title("Customer Risk Profiles")
    try:
        risk_df = load_risk_profiles()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Customers", f"{len(risk_df):,}")
        col2.metric("High Risk", f"{(risk_df['risk_tier']=='HIGH').sum():,}")
        col3.metric("Confirmed Fraud", f"{(risk_df['risk_tier']=='CONFIRMED_FRAUD').sum():,}")

        fig = px.pie(risk_df, names="risk_tier", title="Customer Risk Tier Distribution",
                     color_discrete_map={"LOW": "#22c55e", "MEDIUM": "#f59e0b",
                                        "HIGH": "#ef4444", "CONFIRMED_FRAUD": "#7c3aed"})
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("High Risk Customers")
        high_risk = risk_df[risk_df["risk_tier"].isin(["HIGH", "CONFIRMED_FRAUD"])].sort_values(
            "fraud_rate_pct", ascending=False)
        st.dataframe(high_risk[["customer_id", "total_transactions", "confirmed_fraud_count",
                                 "fraud_rate_pct", "max_distinct_states",
                                 "avg_bureau_score", "risk_tier"]].head(25), use_container_width=True)

    except Exception as e:
        st.error(f"Run the pipeline first.\n\n{e}")

elif page == "Feature Quality Dashboard":
    st.title("Feature Quality & Point-in-Time Integrity")
    st.info("""
    **Why this matters**: All transaction features in this system are computed using only data
    available *before* each transaction's timestamp. This prevents data leakage — the most common
    cause of fraud models that work in backtesting but fail in production.
    """)

    report = load_quality_report()
    if report:
        col1, col2, col3 = st.columns(3)
        col1.metric("Quality Score", f"{report['overall_score']}%")
        col2.metric("Checks Passed", f"{report['passed_checks']}/{report['total_checks']}")
        col3.metric("Status", report["status"])

        checks_df = pd.DataFrame(report["checks"])
        checks_df["icon"] = checks_df["passed"].map({True: "✓", False: "✗"})
        st.dataframe(checks_df[["icon", "check_name", "value", "threshold", "status"]],
                     use_container_width=True)
    else:
        st.warning("Run quality checks first: python src/data_quality_checks.py")

elif page == "Audit Trail & Explainability":
    st.title("Audit Trail & Model Explainability")
    st.markdown("""
    Every risk score produced by this system is **fully auditable**:
    - Each prediction links to a `transaction_id`
    - Each `transaction_id` links to a source batch
    - Each batch links to the raw CSV file with load timestamp
    - Each feature documents its computation logic and temporal window
    """)

    audit = load_audit_trail()
    if audit:
        st.subheader("Sample Transaction Score Explanations")
        for item in audit:
            with st.expander(f"Transaction {item['transaction_id']} — Amount: ${item['amount']:.2f}"):
                col1, col2 = st.columns(2)
                col1.metric("Fraud Probability", f"{item['fraud_probability']:.2%}")
                col2.markdown(f"**Audit Trail**: {item['audit_trail']['data_lineage']}")

                st.markdown("**Top Risk Drivers:**")
                for driver in item["top_risk_drivers"]:
                    st.markdown(f"- **{driver['feature']}**: {driver['value']:.3f} "
                               f"(model importance: {driver['importance']:.3f})")
    else:
        st.warning("Run training first: python src/train_model.py")

elif page == "Model Performance":
    st.title("Fraud Model Performance Summary")

    eval_report = load_eval_report()
    if eval_report:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("AUC-ROC", f"{eval_report['auc_roc']:.4f}")
        col2.metric("AUC-PR", f"{eval_report['auc_pr']:.4f}")
        col3.metric("Precision (Fraud)", f"{eval_report['precision_fraud']:.4f}")
        col4.metric("Recall (Fraud)", f"{eval_report['recall_fraud']:.4f}")

        st.subheader("Top Predictive Features")
        fi_df = pd.DataFrame(eval_report["top_5_features"])
        fig = px.bar(fi_df, x="importance", y="feature", orientation="h",
                     title="Feature Importance (Top 5)", color="importance",
                     color_continuous_scale="Blues")
        st.plotly_chart(fig, use_container_width=True)

        cm = eval_report["confusion_matrix"]
        fig = go.Figure(data=go.Heatmap(
            z=cm, x=["Predicted Legit", "Predicted Fraud"],
            y=["Actual Legit", "Actual Fraud"],
            colorscale="Blues", text=cm, texttemplate="%{text}"
        ))
        fig.update_layout(title="Confusion Matrix")
        st.plotly_chart(fig, use_container_width=True)

        st.info(eval_report["auditability_note"])
    else:
        st.warning("Run model evaluation first: python src/evaluate_model.py")
