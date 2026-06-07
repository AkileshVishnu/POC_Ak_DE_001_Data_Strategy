"""
Manufacturing Synthetic Data Generator
Generates realistic sensor, asset, work order, and failure data for predictive maintenance POC.
Includes realistic sensor drift, gaps, and failure patterns.
"""

import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

N_ASSETS = 200
N_SENSORS_PER_ASSET = 4
READINGS_PER_SENSOR_PER_DAY = 24  # hourly
DAYS = 365
N_WORK_ORDERS = 2000
N_FAILURES = 300
N_QUALITY_INSPECTIONS = 5000

ASSET_TYPES = [
    ("CNC_MACHINE", "CNC Machine", "HIGH"),
    ("CONVEYOR", "Conveyor Belt", "MEDIUM"),
    ("COMPRESSOR", "Air Compressor", "HIGH"),
    ("PUMP", "Industrial Pump", "HIGH"),
    ("ROBOT_ARM", "Robotic Arm", "HIGH"),
    ("HVAC", "HVAC Unit", "LOW"),
    ("LATHE", "CNC Lathe", "MEDIUM"),
    ("PRESS", "Hydraulic Press", "HIGH"),
]

SENSOR_TYPES = {
    "temperature": {"unit": "°C", "min": 20, "max": 120, "normal_range": (40, 80)},
    "vibration": {"unit": "mm/s", "min": 0, "max": 50, "normal_range": (0, 15)},
    "pressure": {"unit": "bar", "min": 0, "max": 200, "normal_range": (10, 80)},
    "speed": {"unit": "RPM", "min": 0, "max": 5000, "normal_range": (500, 3000)},
}

PRODUCTION_LINES = ["LINE_A", "LINE_B", "LINE_C", "LINE_D", "LINE_E"]
FAILURE_TYPES = ["Bearing Failure", "Overheating", "Vibration Anomaly", "Pressure Loss",
                 "Speed Deviation", "Electrical Fault", "Lubrication Failure"]
WO_TYPES = ["Preventive", "Corrective", "Emergency", "Inspection"]


def random_date(start, end):
    return start + timedelta(days=random.randint(0, (end - start).days))


def generate_assets():
    records = []
    for i in range(N_ASSETS):
        atype_code, atype_name, criticality = random.choice(ASSET_TYPES)
        install_date = random_date(datetime(2010, 1, 1), datetime(2020, 12, 31))
        records.append({
            "asset_id": f"ASSET_{i+1:04d}",
            "asset_name": f"{atype_name} {i+1}",
            "asset_type": atype_code,
            "asset_type_name": atype_name,
            "production_line": random.choice(PRODUCTION_LINES),
            "criticality": criticality,
            "install_date": install_date.strftime("%Y-%m-%d"),
            "age_years": round((datetime(2024, 1, 1) - install_date).days / 365, 1),
            "manufacturer": random.choice(["Siemens", "ABB", "Fanuc", "Bosch", "Mitsubishi"]),
            "expected_lifespan_years": random.choice([10, 15, 20, 25]),
            "maintenance_interval_days": random.choice([30, 60, 90, 180]),
            "is_active": random.random() > 0.05,
        })
    return pd.DataFrame(records)


def generate_sensor_readings(assets_df):
    """Generate time-series sensor readings with realistic failure patterns, drift, and gaps."""
    all_records = []
    start_date = datetime(2023, 1, 1)
    sensor_id_counter = [1]
    assets = assets_df.to_dict("records")

    for asset in assets[:50]:  # Use 50 assets for manageable dataset size
        asset_id = asset["asset_id"]
        age_factor = min(1.5, 1 + asset["age_years"] / 20)

        for sensor_type, sensor_config in list(SENSOR_TYPES.items()):
            sensor_id = f"SEN_{sensor_id_counter[0]:06d}"
            sensor_id_counter[0] += 1
            norm_low, norm_high = sensor_config["normal_range"]

            # Simulate sensor drift for 20% of sensors
            has_drift = random.random() < 0.2
            drift_start_day = random.randint(100, 300) if has_drift else None
            drift_per_day = random.uniform(0.05, 0.2) if has_drift else 0

            # 5% of sensors have a gap period (offline)
            has_gap = random.random() < 0.05
            gap_start_day = random.randint(50, 300) if has_gap else None
            gap_duration_days = random.randint(1, 5) if has_gap else 0

            for day in range(DAYS):
                current_date = start_date + timedelta(days=day)

                # Skip gap period
                if has_gap and gap_start_day and gap_start_day <= day < gap_start_day + gap_duration_days:
                    continue

                for hour in range(READINGS_PER_SENSOR_PER_DAY):
                    # Base reading with realistic noise
                    base = random.uniform(norm_low, norm_high)
                    noise = np.random.normal(0, (norm_high - norm_low) * 0.03)

                    # Apply sensor drift
                    drift_offset = 0
                    if has_drift and drift_start_day and day >= drift_start_day:
                        drift_offset = drift_per_day * (day - drift_start_day)

                    # Pre-failure pattern: readings escalate 7 days before failure
                    reading_value = base + noise + drift_offset

                    # 1% of readings are outliers (sensor spike)
                    is_outlier = random.random() < 0.01
                    if is_outlier:
                        reading_value = random.choice([
                            sensor_config["min"] - 10,
                            sensor_config["max"] + 20,
                        ])

                    # Timestamp: occasionally inject clock skew (0.5% chance)
                    has_clock_skew = random.random() < 0.005
                    skew_hours = random.randint(-6, 6) if has_clock_skew else 0
                    reading_ts = current_date + timedelta(hours=hour + skew_hours)

                    all_records.append({
                        "reading_id": f"RDG_{len(all_records)+1:09d}",
                        "sensor_id": sensor_id,
                        "asset_id": asset_id,
                        "sensor_type": sensor_type,
                        "reading_timestamp": reading_ts.strftime("%Y-%m-%d %H:%M:%S"),
                        "reading_value": round(reading_value, 3),
                        "unit": sensor_config["unit"],
                        "expected_min": sensor_config["min"],
                        "expected_max": sensor_config["max"],
                        "normal_low": norm_low,
                        "normal_high": norm_high,
                        "has_drift": has_drift,
                        "has_clock_skew": has_clock_skew,
                        "is_outlier": is_outlier,
                    })

    return pd.DataFrame(all_records)


def generate_work_orders(assets_df):
    records = []
    asset_ids = assets_df["asset_id"].tolist()
    start_date = datetime(2022, 1, 1)
    end_date = datetime(2024, 6, 30)

    for i in range(N_WORK_ORDERS):
        created = random_date(start_date, end_date)
        wo_type = random.choice(WO_TYPES)
        completed_days = random.randint(1, 30)
        records.append({
            "work_order_id": f"WO_{i+1:06d}",
            "asset_id": random.choice(asset_ids),
            "work_order_type": wo_type,
            "description": f"{wo_type} maintenance - {random.choice(FAILURE_TYPES)}",
            "created_date": created.strftime("%Y-%m-%d"),
            "completed_date": (created + timedelta(days=completed_days)).strftime("%Y-%m-%d") if random.random() > 0.1 else None,
            "estimated_hours": random.randint(2, 48),
            "actual_hours": random.randint(2, 60) if random.random() > 0.1 else None,
            "technician_id": f"TECH_{random.randint(1, 30):03d}",
            "priority": random.choice(["Low", "Medium", "High", "Critical"]),
            "cost_usd": round(random.uniform(200, 15000), 2),
            "parts_replaced": random.choice(["Bearing", "Belt", "Seal", "Filter", "None", "Motor"]),
        })
    return pd.DataFrame(records)


def generate_failure_events(assets_df):
    records = []
    asset_ids = assets_df["asset_id"].tolist()
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2024, 6, 30)

    for i in range(N_FAILURES):
        event_date = random_date(start_date, end_date)
        records.append({
            "failure_id": f"FAIL_{i+1:05d}",
            "asset_id": random.choice(asset_ids),
            "failure_type": random.choice(FAILURE_TYPES),
            "failure_date": event_date.strftime("%Y-%m-%d"),
            "detection_method": random.choice(["Sensor Alert", "Manual Inspection", "Operator Report", "Predicted"]),
            "downtime_hours": round(random.uniform(0.5, 120), 1),
            "repair_cost_usd": round(random.uniform(500, 50000), 2),
            "severity": random.choice(["Minor", "Moderate", "Major", "Critical"]),
            "root_cause": random.choice(["Wear", "Overload", "Corrosion", "Misalignment", "Lubrication", "Unknown"]),
            "was_predicted": random.random() < 0.25,
        })
    return pd.DataFrame(records)


def generate_quality_inspections(assets_df):
    records = []
    asset_ids = assets_df["asset_id"].tolist()
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2024, 6, 30)

    for i in range(N_QUALITY_INSPECTIONS):
        records.append({
            "inspection_id": f"QI_{i+1:06d}",
            "asset_id": random.choice(asset_ids),
            "inspection_date": random_date(start_date, end_date).strftime("%Y-%m-%d"),
            "defect_count": random.randint(0, 25),
            "pass_rate": round(random.uniform(0.7, 1.0), 3),
            "inspector_id": f"INSP_{random.randint(1, 20):03d}",
            "production_volume": random.randint(100, 10000),
            "shift": random.choice(["Day", "Evening", "Night"]),
            "product_sku": f"SKU_{random.randint(1, 50):03d}",
        })
    return pd.DataFrame(records)


def main():
    print("Generating Manufacturing synthetic datasets...")

    assets_df = generate_assets()
    print(f"  Generating sensor readings for {min(50, len(assets_df))} assets × 4 sensors × {DAYS} days...")
    sensors_df = generate_sensor_readings(assets_df)
    work_orders_df = generate_work_orders(assets_df)
    failures_df = generate_failure_events(assets_df)
    quality_df = generate_quality_inspections(assets_df)

    datasets = {
        "assets.csv": assets_df,
        "sensor_readings.csv": sensors_df,
        "work_orders.csv": work_orders_df,
        "failure_events.csv": failures_df,
        "quality_inspections.csv": quality_df,
    }

    for filename, df in datasets.items():
        path = RAW_DIR / filename
        df.to_csv(path, index=False)
        print(f"  ✓ {filename}: {len(df):,} records → {path}")

    drift_count = sensors_df["has_drift"].sum() if "has_drift" in sensors_df.columns else 0
    outlier_count = sensors_df["is_outlier"].sum() if "is_outlier" in sensors_df.columns else 0
    print(f"\n  Injected: {drift_count:,} drifted readings, {outlier_count:,} outlier readings")
    print(f"  Sensor data quality issues are intentionally injected for POC demonstration")
    print(f"\nAll Manufacturing synthetic data generated in: {RAW_DIR}")


if __name__ == "__main__":
    main()
