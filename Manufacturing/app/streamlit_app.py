"""
Manufacturing Predictive Maintenance Dashboard
Provides: Asset Health, Sensor Quality, Failure Risk, Maintenance Recommendations.
"""

import json
import duckdb
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "manufacturing.duckdb"
OUTPUTS_DIR = BASE_DIR / "outputs"

st.set_page_config(
    page_title="Manufacturing Predictive Maintenance",
    page_icon="🏭",
    layout="wide",
)


@st.cache_data(ttl=300)
def load_asset_health():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    return con.execute("SELECT * FROM gold_asset_health_summary").df()


@st.cache_data(ttl=300)
def load_sensor_quality():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    return con.execute("SELECT * FROM gold_sensor_quality_score").df()


@st.cache_data(ttl=300)
def load_features():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    return con.execute("SELECT * FROM gold_failure_prediction_features LIMIT 20000").df()


@st.cache_data(ttl=300)
def load_maintenance():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    return con.execute("SELECT * FROM gold_maintenance_recommendations ORDER BY maintenance_priority_score DESC").df()


def load_quality_report():
    p = OUTPUTS_DIR / "quality_report.json"
    return json.load(open(p)) if p.exists() else None


def load_eval_report():
    p = OUTPUTS_DIR / "model_evaluation.json"
    return json.load(open(p)) if p.exists() else None


st.sidebar.title("🏭 Predictive Maintenance")
st.sidebar.markdown("Time-Series Data Quality Strategy")
page = st.sidebar.radio("Navigate", [
    "Asset Health Overview", "Sensor Quality Dashboard",
    "Failure Risk Dashboard", "Maintenance Recommendations",
    "Data Quality Scorecard"
])

if page == "Asset Health Overview":
    st.title("Asset Health Overview")
    try:
        df = load_asset_health()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Assets", len(df))
        col2.metric("Avg Health Score", f"{df['asset_health_score'].mean():.1f}/100")
        col3.metric("Overdue Maintenance", f"{(df['maintenance_urgency']=='OVERDUE').sum()}")
        col4.metric("High Criticality", f"{(df['criticality']=='HIGH').sum()}")

        col_l, col_r = st.columns(2)
        with col_l:
            fig = px.scatter(df, x="age_years", y="asset_health_score",
                             color="criticality", size="failure_count_12m",
                             hover_data=["asset_name", "production_line", "maintenance_urgency"],
                             title="Asset Health vs Age",
                             color_discrete_map={"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#22c55e"})
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            urgency_counts = df["maintenance_urgency"].value_counts().reset_index()
            urgency_counts.columns = ["urgency", "count"]
            fig = px.pie(urgency_counts, names="urgency", values="count",
                         title="Maintenance Urgency Distribution",
                         color_discrete_map={"OVERDUE": "#ef4444", "DUE_SOON": "#f59e0b", "ON_SCHEDULE": "#22c55e"})
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Low Health Score Assets (Score < 50)")
        low_health = df[df["asset_health_score"] < 50].sort_values("asset_health_score")[
            ["asset_id", "asset_name", "asset_type", "criticality", "asset_health_score",
             "failure_count_12m", "maintenance_urgency", "days_since_last_maintenance"]
        ]
        st.dataframe(low_health, use_container_width=True)
    except Exception as e:
        st.error(f"Run the pipeline first: python src/run_pipeline.py\n\n{e}")

elif page == "Sensor Quality Dashboard":
    st.title("Sensor Quality Dashboard")
    st.info("""
    **Why this matters**: Poor sensor quality is invisible to the AI model — it will simply
    learn to predict based on corrupted signals. Sensor quality scores gate which readings
    are used in rolling features and flag predictions with reduced confidence.
    """)
    try:
        df = load_sensor_quality()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Sensors Monitored", len(df))
        col2.metric("Avg Sensor Quality", f"{df['sensor_quality_score'].mean():.1f}/100")
        col3.metric("Low Quality Sensors", f"{(df['sensor_quality_score'] < 60).sum()}")

        fig = px.histogram(df, x="sensor_quality_score", color="sensor_type",
                           nbins=20, title="Sensor Quality Score Distribution by Type")
        st.plotly_chart(fig, use_container_width=True)

        col_l, col_r = st.columns(2)
        with col_l:
            fig = px.scatter(df, x="validity_rate_pct", y="sensor_quality_score",
                             color="sensor_type", size="total_readings",
                             hover_data=["sensor_id", "asset_id", "anomaly_count"],
                             title="Validity Rate vs Quality Score")
            st.plotly_chart(fig, use_container_width=True)
        with col_r:
            st.subheader("Sensors Needing Attention (Quality < 60)")
            low_q = df[df["sensor_quality_score"] < 60].sort_values("sensor_quality_score")[
                ["sensor_id", "asset_id", "sensor_type", "sensor_quality_score",
                 "validity_rate_pct", "anomaly_count", "hard_outlier_count"]
            ]
            st.dataframe(low_q.head(20), use_container_width=True)
    except Exception as e:
        st.error(f"Run the pipeline first.\n\n{e}")

elif page == "Failure Risk Dashboard":
    st.title("Failure Risk Dashboard")
    try:
        df = load_features()
        if "failure_in_next_7d" in df.columns:
            col1, col2 = st.columns(2)
            col1.metric("Total Asset-Day Records", f"{len(df):,}")
            col2.metric("Days with Failure in 7d", f"{df['failure_in_next_7d'].sum():,}")

            fig = px.scatter(df.sample(min(2000, len(df))),
                             x="total_anomalies_day", y="avg_vibration",
                             color=df.sample(min(2000, len(df)))["failure_in_next_7d"].astype(str),
                             title="Anomaly Count vs Vibration by Failure Label",
                             color_discrete_map={"0": "#22c55e", "1": "#ef4444"})
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Run the pipeline first.\n\n{e}")

elif page == "Maintenance Recommendations":
    st.title("Maintenance Recommendations")
    try:
        df = load_maintenance()
        col1, col2, col3 = st.columns(3)
        col1.metric("Emergency Actions", f"{(df['recommended_action_tier']=='EMERGENCY').sum()}")
        col2.metric("High Priority", f"{(df['recommended_action_tier']=='HIGH').sum()}")
        col3.metric("Avg Priority Score", f"{df['maintenance_priority_score'].mean():.1f}")

        colors = {"EMERGENCY": "#7c3aed", "HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#22c55e"}
        fig = px.bar(df.head(20), x="asset_name", y="maintenance_priority_score",
                     color="recommended_action_tier", color_discrete_map=colors,
                     title="Top 20 Assets by Maintenance Priority",
                     hover_data=["criticality", "days_since_last_maintenance",
                                 "asset_health_score", "failure_count_12m"])
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Prioritized Maintenance Queue")
        st.dataframe(df[["asset_id", "asset_name", "asset_type", "criticality",
                          "recommended_action_tier", "maintenance_priority_score",
                          "asset_health_score", "days_since_last_maintenance",
                          "failure_count_12m", "avg_sensor_quality_score"]].head(50),
                     use_container_width=True)
    except Exception as e:
        st.error(f"Run the pipeline first.\n\n{e}")

elif page == "Data Quality Scorecard":
    st.title("Time-Series Data Quality Scorecard")
    report = load_quality_report()
    if report:
        col1, col2, col3 = st.columns(3)
        col1.metric("Quality Score", f"{report['overall_score']}%")
        col2.metric("Checks", f"{report['passed_checks']}/{report['total_checks']}")
        col3.metric("Status", report["status"])

        checks_df = pd.DataFrame(report["checks"])
        checks_df["icon"] = checks_df["passed"].map({True: "✓", False: "✗"})
        st.dataframe(checks_df[["icon", "check_name", "value", "threshold", "status"]],
                     use_container_width=True)

        eval_report = load_eval_report()
        if eval_report:
            st.subheader("Model Performance")
            col1, col2, col3 = st.columns(3)
            col1.metric("AUC-ROC", f"{eval_report['auc_roc']:.4f}")
            col2.metric("Recall (Failure)", f"{eval_report['recall_failure']:.4f}")
            col3.metric("Precision (Failure)", f"{eval_report['precision_failure']:.4f}")
            st.info(eval_report.get("data_quality_note", ""))
    else:
        st.warning("Run: python src/data_quality_checks.py")
