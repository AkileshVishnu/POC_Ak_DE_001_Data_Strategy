"""
Healthcare HCP Targeting Streamlit Dashboard
Provides interactive views of:
  - HCP Targeting Overview
  - HCP 360 Profile
  - Territory Summary
  - Data Quality Scorecard
"""

import json
import duckdb
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "healthcare.duckdb"
OUTPUTS_DIR = BASE_DIR / "outputs"

st.set_page_config(
    page_title="Healthcare HCP Intelligence",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_resource
def get_connection():
    return duckdb.connect(str(DB_PATH), read_only=True)


@st.cache_data(ttl=300)
def load_hcp_targeting():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    return con.execute("SELECT * FROM gold_hcp_targeting_score").df()


@st.cache_data(ttl=300)
def load_hcp_360():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    return con.execute("SELECT * FROM gold_hcp_360").df()


@st.cache_data(ttl=300)
def load_trial_sites():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    return con.execute("SELECT * FROM gold_trial_site_priority").df()


@st.cache_data(ttl=300)
def load_psp_summary():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    return con.execute("SELECT * FROM gold_patient_support_summary").df()


def load_quality_report():
    path = OUTPUTS_DIR / "quality_report.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("🏥 HCP Intelligence")
st.sidebar.markdown("Healthcare MDM-First Data Product Strategy")
page = st.sidebar.radio(
    "Navigate",
    ["HCP Targeting Overview", "HCP 360 Profile", "Territory Summary",
     "Trial Site Prioritization", "Data Quality Scorecard"]
)

# ── Pages ──────────────────────────────────────────────────────────────────────

if page == "HCP Targeting Overview":
    st.title("HCP Targeting Overview")
    st.caption("AI-scored targeting priorities based on unified HCP master data")

    try:
        df = load_hcp_targeting()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total HCPs", f"{len(df):,}")
        col2.metric("Priority A HCPs", f"{(df['targeting_priority']=='A').sum():,}")
        col3.metric("Avg Engagement Score", f"{df['engagement_score'].mean():.1f}")
        col4.metric("HCPs with Recent Activity", f"{(df['days_since_last_interaction'] <= 90).sum():,}")

        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Targeting Priority Distribution")
            priority_counts = df["targeting_priority"].value_counts().reset_index()
            priority_counts.columns = ["Priority", "Count"]
            priority_counts = priority_counts.sort_values("Priority")
            colors = {"A": "#22c55e", "B": "#3b82f6", "C": "#f59e0b", "D": "#ef4444"}
            fig = px.bar(priority_counts, x="Priority", y="Count",
                         color="Priority", color_discrete_map=colors,
                         title="HCP Count by Targeting Tier")
            st.plotly_chart(fig, use_container_width=True)

        with col_right:
            st.subheader("Engagement Score Distribution")
            fig = px.histogram(df, x="engagement_score", nbins=30,
                               color="targeting_priority",
                               color_discrete_map={"A": "#22c55e", "B": "#3b82f6", "C": "#f59e0b", "D": "#ef4444"},
                               title="Engagement Score by Priority Tier")
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Top Priority A HCPs")
        top_a = df[df["targeting_priority"] == "A"].nlargest(20, "engagement_score")[
            ["hcp_id", "specialty_tier", "state", "territory_id",
             "engagement_score", "total_rx_12m", "interactions_90d", "targeting_priority"]
        ]
        st.dataframe(top_a, use_container_width=True)

        st.subheader("Interactions vs Prescriptions by Priority")
        fig = px.scatter(df.sample(min(500, len(df))),
                         x="interactions_90d", y="total_rx_12m",
                         color="targeting_priority",
                         color_discrete_map={"A": "#22c55e", "B": "#3b82f6", "C": "#f59e0b", "D": "#ef4444"},
                         size="engagement_score", hover_data=["hcp_id", "state"],
                         title="Interactions (90d) vs Total Rx (12m)")
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Data not available. Run the pipeline first: python src/run_pipeline.py\n\nError: {e}")

elif page == "HCP 360 Profile":
    st.title("HCP 360 Profile")
    st.caption("Unified golden record view for individual HCP deep-dive")

    try:
        df360 = load_hcp_360()
        hcp_options = df360["hcp_id"].tolist()
        selected_hcp = st.selectbox("Select HCP", hcp_options[:200])

        hcp = df360[df360["hcp_id"] == selected_hcp].iloc[0]

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(f"### {hcp['full_name']}")
            st.markdown(f"**Specialty**: {hcp['specialty_name']} ({hcp['specialty_tier']})")
            st.markdown(f"**State**: {hcp['state']}")
            st.markdown(f"**NPI**: {hcp['npi']}")
            st.markdown(f"**Degree**: {hcp['degree']}")
            st.markdown(f"**Years in Practice**: {hcp['years_in_practice']}")
            st.markdown(f"**KOL**: {'Yes' if hcp['is_kol'] else 'No'}")
            st.markdown(f"**Investigator**: {'Yes' if hcp['is_investigator'] else 'No'}")

        with col2:
            metrics = {
                "Engagement Score": hcp["engagement_score"],
                "Interactions (12m)": hcp["total_interactions_12m"],
                "Interactions (90d)": hcp["interactions_90d"],
                "Rx Volume (12m)": hcp["total_rx_12m"],
                "New Starts (12m)": hcp["total_new_starts_12m"],
                "PSP Cases": hcp["total_psp_cases"],
            }
            fig = go.Figure(go.Bar(
                x=list(metrics.keys()),
                y=list(metrics.values()),
                marker_color="#3b82f6"
            ))
            fig.update_layout(title="HCP Signal Profile")
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Data Quality Status")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("NPI Valid", "✓" if hcp["dq_npi_valid"] else "✗")
        col_b.metric("Name Complete", "✓" if hcp["dq_name_complete"] else "✗")
        col_c.metric("Territory Assigned", hcp["territory_id"])

    except Exception as e:
        st.error(f"Data not available. Run the pipeline first.\n\nError: {e}")

elif page == "Territory Summary":
    st.title("Territory Performance Summary")

    try:
        df = load_hcp_targeting()
        terr_summary = df.groupby("territory_id").agg(
            hcp_count=("hcp_id", "count"),
            a_priority_count=("targeting_priority", lambda x: (x == "A").sum()),
            avg_engagement=("engagement_score", "mean"),
            total_rx=("total_rx_12m", "sum"),
        ).reset_index()
        terr_summary["a_priority_pct"] = (terr_summary["a_priority_count"] / terr_summary["hcp_count"] * 100).round(1)

        st.subheader("Territory KPIs")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Territories", len(terr_summary))
        col2.metric("Avg HCPs per Territory", f"{terr_summary['hcp_count'].mean():.0f}")
        col3.metric("Avg Engagement Score", f"{terr_summary['avg_engagement'].mean():.1f}")

        fig = px.bar(terr_summary.sort_values("avg_engagement", ascending=False).head(20),
                     x="territory_id", y="avg_engagement",
                     color="a_priority_pct",
                     color_continuous_scale="RdYlGn",
                     title="Average Engagement Score by Territory (Top 20)")
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(terr_summary.sort_values("a_priority_pct", ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"Data not available. Run the pipeline first.\n\nError: {e}")

elif page == "Trial Site Prioritization":
    st.title("Clinical Trial Site Prioritization")

    try:
        df = load_trial_sites()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Sites", len(df))
        col2.metric("High Priority Sites", f"{(df['priority_tier']=='HIGH').sum()}")
        col3.metric("Avg Site Quality Score", f"{df['site_quality_score'].mean():.1f}")

        fig = px.scatter(df, x="enrolled_patients", y="site_quality_score",
                         color="priority_tier", size="enrolled_patients",
                         hover_data=["site_id", "hco_name", "state", "site_rating"],
                         title="Site Quality Score vs Enrollment",
                         color_discrete_map={"HIGH": "#22c55e", "MEDIUM": "#3b82f6", "LOW": "#ef4444"})
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Top Priority Sites")
        top_sites = df[df["priority_tier"] == "HIGH"].nlargest(15, "site_quality_score")[
            ["site_id", "hco_name", "state", "enrolled_patients",
             "site_rating", "site_quality_score", "priority_tier"]
        ]
        st.dataframe(top_sites, use_container_width=True)

    except Exception as e:
        st.error(f"Data not available. Run the pipeline first.\n\nError: {e}")

elif page == "Data Quality Scorecard":
    st.title("Data Quality Scorecard")
    st.caption("End-to-end quality monitoring across Bronze → Silver → Gold layers")

    report = load_quality_report()
    if report:
        col1, col2, col3, col4 = st.columns(4)
        status_color = {"HEALTHY": "green", "DEGRADED": "orange", "CRITICAL": "red"}
        col1.metric("Overall Score", f"{report['overall_score']}%")
        col2.metric("Passed Checks", f"{report['passed_checks']}/{report['total_checks']}")
        col3.metric("Status", report["status"])
        col4.metric("Generated At", report["report_generated_at"][:10])

        st.subheader("Individual Check Results")
        checks_df = pd.DataFrame(report["checks"])
        checks_df["icon"] = checks_df["passed"].map({True: "✓", False: "✗"})
        st.dataframe(
            checks_df[["icon", "check_name", "value", "threshold", "status"]],
            use_container_width=True
        )

        if report.get("failed_check_names"):
            st.error("Failed Checks:\n" + "\n".join(f"• {c}" for c in report["failed_check_names"]))
    else:
        st.warning("No quality report found. Run: python src/data_quality_checks.py")
