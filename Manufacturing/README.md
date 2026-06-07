# Manufacturing POC
## Time-Series Data Quality Strategy for Predictive Maintenance AI

---

## Business Problem

A manufacturing company operates hundreds of pieces of critical equipment across multiple production lines. They need to:

1. **Predict equipment failures** before they occur (avoiding unplanned downtime)
2. **Prioritize maintenance work orders** based on actual asset health
3. **Monitor quality inspection results** in correlation with equipment condition

**The failure mode without data strategy**: Predictive maintenance AI is trained on sensor data. If that sensor data has gaps, drifts, incorrect timestamps, or invalid readings, the AI model learns to predict noise instead of actual failure patterns.

**Real consequence**: A sensor on a critical CNC machine develops a systematic -12°C drift over 6 months. The temperature readings stay within the "normal" range but are consistently underestimated. The predictive maintenance model misses the failure signal. A catastrophic bearing failure costs $2M in damage and 3 weeks of downtime.

**This POC proves that predictive maintenance AI is only as good as the time-series data quality that feeds it.**

---

## Why AI Fails Without Upstream Data Strategy

```mermaid
flowchart TD
    subgraph Without["❌ Without Time-Series Data Quality Strategy"]
        W1[Sensor reading: temp=72°C\nActual: 84°C — sensor drifted]
        W2[Data gap: 4 hours missing\nNot detected or flagged]
        W3[Timestamp: 2024-01-15 03:00\nActual: 2024-01-15 13:00 — clock skew]
        W4[Model receives corrupted time-series]
        W5[Rolling features computed on gappy data]
        W6[AI misses failure signal\nMachine fails → $2M damage]
        W1 & W2 & W3 --> W4 --> W5 --> W6
    end

    subgraph With["✅ With Time-Series Data Quality Strategy"]
        M1[Sensor reading validated against physical limits]
        M2[Gap detection flags 4-hour outage\nSensor quality score = 0.6 for affected window]
        M3[Timestamp anomaly detected and corrected]
        M4[Rolling features computed on validated data]
        M5[AI receives clean signal with quality scores]
        M6[Failure predicted 3 weeks early\nMaintenance scheduled proactively]
        M1 & M2 & M3 --> M4 --> M5 --> M6
    end
```

---

## Data Strategy: Time-Series Quality and Asset Data Product

### Core Approach

1. **Asset hierarchy data product**: Every sensor reading is contextualized by asset type, age, and criticality
2. **Timestamp quality enforcement**: Clock skew, duplicate timestamps, and ordering violations are detected and flagged
3. **Sensor range validation**: Physical bounds are defined per sensor type and violated readings are flagged
4. **Gap detection and imputation**: Missing sensor readings are detected, counted, and handled explicitly
5. **Rolling window feature engineering**: Features computed over validated, gap-aware time windows
6. **Sensor quality scoring**: Each sensor has a quality score that gates its use in ML features

---

## Architecture Diagram

```mermaid
flowchart TD
    SCADA[SCADA System\nSensor Readings] --> B1
    CMMS[CMMS\nWork Orders] --> B1
    ERP[ERP\nAsset Registry] --> B1
    QI[Quality Inspection\nSystem] --> B1

    subgraph B1["🥉 Bronze Layer"]
        BS[bronze_sensor_readings]
        BW[bronze_work_orders]
        BA[bronze_assets]
        BQ[bronze_quality_inspections]
        BF[bronze_failure_events]
    end

    B1 --> SL

    subgraph SL["🥈 Silver Layer — Time-Series Validation"]
        SS[silver_sensors_clean\nRange validated; gaps flagged]
        SW[silver_work_orders_clean]
        SA[silver_assets_clean]
        SQ[silver_quality_clean]
        SFE[silver_failure_events_clean]
    end

    SL --> GL

    subgraph GL["🥇 Gold Layer — Asset Data Products"]
        GAH[gold_asset_health_summary\nPer-asset health + failure risk]
        GSQ[gold_sensor_quality_score\nPer-sensor quality metrics]
        GFP[gold_failure_prediction_features\nRolling-window ML features]
        GMR[gold_maintenance_recommendations\nPriority scoring]
    end

    GL --> AI

    subgraph AI["🤖 AI / ML Layer"]
        FM[Failure Risk Classifier\nRandom Forest]
        EXP[SHAP Explainability]
    end

    AI --> DB

    subgraph DB["📊 Streamlit Dashboard"]
        D1[Asset Health Overview]
        D2[Sensor Quality Dashboard]
        D3[Failure Risk Dashboard]
        D4[Maintenance Recommendations]
    end

    subgraph OBS["🔍 Observability"]
        TSQ[Timestamp Quality Checks]
        GD[Gap Detection Metrics]
        DR[Drift Detection]
    end

    SL -.-> OBS
    GL -.-> OBS
```

---

## Data Model Overview

| Entity | Table | Records (Synthetic) |
|--------|-------|---------------------|
| Assets / Equipment | `silver_assets_clean` | 200 |
| Sensor Readings | `silver_sensors_clean` | 500,000 |
| Work Orders | `silver_work_orders_clean` | 2,000 |
| Failure Events | `silver_failure_events_clean` | 300 |
| Quality Inspections | `silver_quality_clean` | 5,000 |

---

## Why Time-Series Data Quality Is Critical for Predictive Maintenance AI

### 1. Timestamp Quality
Sensor readings arrive from SCADA systems that may have clock drift, network delays, or batch processing delays. A timestamp error of ±4 hours can make a failure signal appear before or after the actual event, corrupting the model's understanding of failure progression.

### 2. Sensor Range Validation
Physical sensors have physical limits. A temperature sensor reporting -273°C is clearly invalid. But what about a temperature reading 15% below the expected range? That may indicate sensor drift — not an obvious violation, but a signal that the sensor is no longer reliable.

### 3. Gap Detection
When a sensor goes offline for 4 hours, the data pipeline may fill the gap with nulls, zeros, or carry-forward the last value. None of these is correct. The gap must be detected, documented, and the affected features must be flagged with reduced confidence.

### 4. Rolling Window Feature Integrity
A 24-hour rolling average computed over a window with a 4-hour gap is not the same as one computed over complete data. The imputed values change the mean, the variance, and the trend signal. Rolling features must be annotated with the data completeness of their input window.

---

## How to Run Locally

```bash
cd Manufacturing
python src/generate_synthetic_data.py
python src/run_pipeline.py
python src/data_quality_checks.py
python src/train_model.py
python src/evaluate_model.py
streamlit run app/streamlit_app.py
```

---

## Expected Outputs

- `data/gold/*.parquet` — Gold asset and sensor data products
- `manufacturing.duckdb` — Analytical database
- `models/failure_prediction_model.joblib` — Trained model
- `outputs/quality_report.json` — Sensor and timestamp quality report
- `outputs/model_evaluation.json` — Model performance metrics
- Streamlit dashboard at http://localhost:8503
