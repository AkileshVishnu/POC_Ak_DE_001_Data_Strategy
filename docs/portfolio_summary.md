# Portfolio Summary

## What This Repository Demonstrates

This repository is a technical portfolio demonstrating senior-level capability across the full data-to-AI stack. It is organized around a single central thesis: **upstream data engineering strategy determines downstream AI reliability**.

## Skills Matrix

| Skill Area | Demonstrated In | Evidence |
|------------|----------------|---------|
| Data Architecture Design | All 3 projects | Medallion + industry-specific extensions |
| MDM and Entity Resolution | Healthcare | Golden HCP record from multiple sources |
| Point-in-Time Feature Engineering | Finance | Temporal feature correctness, leakage prevention |
| Time-Series Data Engineering | Manufacturing | Sensor gap handling, rolling windows, drift detection |
| dbt Core Data Modeling | All 3 projects | Bronze/Silver/Gold SQL models with tests |
| Great Expectations | All 3 projects | Expectation suites, quality reports |
| DuckDB | All 3 projects | Local OLAP analytical engine |
| Python Pipeline Engineering | All 3 projects | Modular, tested, reproducible pipelines |
| scikit-learn ML Modeling | All 3 projects | Classification, scoring, anomaly detection |
| Model Explainability | All 3 projects | SHAP values, feature importance |
| Streamlit Dashboards | All 3 projects | Interactive monitoring and KPI dashboards |
| Data Governance Documentation | All 3 projects | Lineage, governance, compliance docs |
| Technical Documentation | All 3 projects | Strategy, architecture, KPI, data model docs |
| pytest Testing | All 3 projects | Unit and integration tests |

## Project Summaries

### Healthcare / Pharma
**Strategy**: MDM-First Governed Data Product
**AI Use Case**: HCP targeting and clinical trial site prioritization
**Key Insight**: Without a golden HCP record from MDM, AI targeting systems will over-target duplicated records and under-serve truly high-priority physicians.

### Finance
**Strategy**: Point-in-Time Feature Quality and Auditability
**AI Use Case**: Fraud detection and risk scoring
**Key Insight**: Fraud models trained without point-in-time correctness appear accurate in backtesting and fail immediately in production — feature freshness and temporal integrity are the difference between a working model and a liability.

### Manufacturing
**Strategy**: Time-Series Data Quality and Asset Data Products
**AI Use Case**: Predictive maintenance failure prediction
**Key Insight**: A predictive maintenance model is only as reliable as its sensor data. Timestamp errors, sensor drift, and missing readings are invisible to the model — they silently degrade accuracy until a failure occurs.

## How to Navigate This Repository

1. **Start here**: Read the root [README.md](../README.md) for the central thesis
2. **Go deeper**: Read [docs/upstream_vs_downstream_ai.md](upstream_vs_downstream_ai.md)
3. **Understand the framework**: Read [docs/ai_ready_data_strategy_framework.md](ai_ready_data_strategy_framework.md)
4. **Pick a project**: Each project folder has its own README and docs/ folder
5. **Run the code**: Follow the Makefile commands to run each project locally

## Target Audience

This portfolio is designed for:
- **Data Engineering interviews**: Demonstrates medallion architecture, dbt, quality engineering
- **AI Engineering interviews**: Demonstrates feature engineering, ML pipelines, model evaluation
- **Solutions Architect roles**: Demonstrates cross-stack design thinking and documentation
- **Technical leadership roles**: Demonstrates strategic thinking about data and AI alignment
- **LinkedIn posts and articles**: Each project tells a clear story about why data strategy matters
