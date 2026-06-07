"""
Healthcare Synthetic Data Generator
Generates all synthetic CSV datasets for the Healthcare POC.
No real PHI, PII, or clinical data is used.
"""

import os
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

# ── Constants ─────────────────────────────────────────────────────────────────

N_HCPS = 2000
N_HCOS = 500
N_TERRITORIES = 40
N_INTERACTIONS = 15000
N_TRIAL_SITES = 200
N_PATIENT_CASES = 3000

SPECIALTIES = [
    ("ONCO", "Oncology", "A"),
    ("CARDIO", "Cardiology", "A"),
    ("NEURO", "Neurology", "B"),
    ("ENDO", "Endocrinology", "B"),
    ("RHEUM", "Rheumatology", "B"),
    ("GASTRO", "Gastroenterology", "C"),
    ("PULM", "Pulmonology", "C"),
    ("NEPHRO", "Nephrology", "C"),
    ("DERM", "Dermatology", "D"),
    ("PCP", "Primary Care", "D"),
]

HCO_TYPES = ["Hospital", "Academic Medical Center", "Community Clinic", "Specialty Center", "Cancer Center"]
STATES = ["CA", "TX", "FL", "NY", "PA", "OH", "IL", "GA", "NC", "MI",
          "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI"]
PRODUCTS = ["PRODUCT_A", "PRODUCT_B", "PRODUCT_C"]
INTERACTION_TYPES = ["In-Person Visit", "Phone Call", "Email", "Webinar", "Conference", "Sample Drop"]
SOURCES = ["CRM", "RX_FEED", "SPEAKER_BUREAU", "EHR_INTEGRATION"]


def random_npi():
    return str(random.randint(1000000000, 1999999999))


def random_date(start_date, end_date):
    delta = end_date - start_date
    return start_date + timedelta(days=random.randint(0, delta.days))


def generate_hcp_master():
    """Generate the golden HCP master dataset."""
    records = []
    npis = set()
    first_names = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
                   "William", "Barbara", "David", "Susan", "Richard", "Jessica", "Joseph", "Sarah",
                   "Thomas", "Karen", "Charles", "Lisa", "Christopher", "Nancy", "Daniel", "Betty",
                   "Matthew", "Margaret", "Anthony", "Sandra", "Donald", "Ashley"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
                  "Wilson", "Anderson", "Taylor", "Thomas", "Jackson", "White", "Harris", "Martin",
                  "Thompson", "Moore", "Young", "Allen", "King", "Wright", "Scott", "Torres",
                  "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson"]

    for i in range(N_HCPS):
        npi = random_npi()
        while npi in npis:
            npi = random_npi()
        npis.add(npi)

        spec_code, spec_name, spec_tier = random.choice(SPECIALTIES)
        state = random.choice(STATES)
        territory_id = f"TER_{random.randint(1, N_TERRITORIES):03d}"
        fname = random.choice(first_names)
        lname = random.choice(last_names)

        records.append({
            "hcp_id": f"HCP_{i+1:05d}",
            "npi": npi,
            "first_name": fname,
            "last_name": lname,
            "full_name": f"Dr. {fname} {lname}",
            "specialty_code": spec_code,
            "specialty_name": spec_name,
            "specialty_tier": spec_tier,
            "state": state,
            "territory_id": territory_id,
            "degree": random.choice(["MD", "DO", "PhD", "PharmD"]),
            "years_in_practice": random.randint(1, 35),
            "is_key_opinion_leader": random.random() < 0.08,
            "is_investigator": random.random() < 0.05,
            "created_date": random_date(datetime(2018, 1, 1), datetime(2022, 12, 31)).strftime("%Y-%m-%d"),
            "updated_date": random_date(datetime(2023, 1, 1), datetime(2024, 6, 30)).strftime("%Y-%m-%d"),
        })

    return pd.DataFrame(records)


def generate_hco_master():
    """Generate Healthcare Organization master data."""
    records = []
    for i in range(N_HCOS):
        hco_type = random.choice(HCO_TYPES)
        state = random.choice(STATES)
        city_map = {"CA": "Los Angeles", "TX": "Houston", "FL": "Miami", "NY": "New York",
                    "PA": "Philadelphia", "OH": "Columbus", "IL": "Chicago"}
        city = city_map.get(state, f"{state}_City")

        records.append({
            "hco_id": f"HCO_{i+1:04d}",
            "hco_name": f"{city} {hco_type} {random.randint(1, 9)}",
            "hco_type": hco_type,
            "state": state,
            "city": city,
            "bed_count": random.randint(50, 1200) if hco_type in ["Hospital", "Academic Medical Center"] else None,
            "is_teaching": random.random() < 0.25,
            "is_nci_designated": hco_type == "Cancer Center" and random.random() < 0.4,
            "created_date": random_date(datetime(2018, 1, 1), datetime(2021, 12, 31)).strftime("%Y-%m-%d"),
        })

    return pd.DataFrame(records)


def generate_hcp_hco_affiliations(hcp_df, hco_df):
    """Generate HCP-HCO affiliation records."""
    records = []
    hcp_ids = hcp_df["hcp_id"].tolist()
    hco_ids = hco_df["hco_id"].tolist()

    for hcp_id in hcp_ids:
        n_affiliations = np.random.choice([1, 2, 3], p=[0.6, 0.3, 0.1])
        for _ in range(n_affiliations):
            records.append({
                "affiliation_id": f"AFF_{len(records)+1:06d}",
                "hcp_id": hcp_id,
                "hco_id": random.choice(hco_ids),
                "affiliation_type": random.choice(["Primary", "Secondary", "Admitting", "Consulting"]),
                "is_primary": len(records) == 0,
                "start_date": random_date(datetime(2015, 1, 1), datetime(2022, 12, 31)).strftime("%Y-%m-%d"),
            })

    return pd.DataFrame(records)


def generate_interactions(hcp_df):
    """Generate HCP interaction/call activity data."""
    records = []
    hcp_ids = hcp_df["hcp_id"].tolist()
    end_date = datetime(2024, 6, 30)
    start_date = datetime(2022, 1, 1)

    for _ in range(N_INTERACTIONS):
        hcp_id = random.choice(hcp_ids)
        product = random.choice(PRODUCTS)
        itype = random.choice(INTERACTION_TYPES)
        idate = random_date(start_date, end_date)

        records.append({
            "interaction_id": f"INT_{len(records)+1:07d}",
            "hcp_id": hcp_id,
            "rep_id": f"REP_{random.randint(1, 200):04d}",
            "product": product,
            "interaction_type": itype,
            "interaction_date": idate.strftime("%Y-%m-%d"),
            "duration_minutes": random.randint(5, 45) if itype != "Email" else None,
            "outcome": random.choice(["Positive", "Neutral", "Negative", "No Contact"]),
            "samples_dropped": random.randint(0, 12) if itype == "Sample Drop" else 0,
            "source_system": "CRM",
        })

    return pd.DataFrame(records)


def generate_rx_aggregates(hcp_df):
    """Generate prescription aggregate data (not patient-level)."""
    records = []
    hcp_ids = hcp_df["hcp_id"].tolist()

    for hcp_id in hcp_ids:
        for product in PRODUCTS:
            if random.random() < 0.7:
                records.append({
                    "rx_id": f"RX_{len(records)+1:07d}",
                    "hcp_id": hcp_id,
                    "product": product,
                    "period_month": random.randint(1, 12),
                    "period_year": random.randint(2022, 2024),
                    "total_rx_count": random.randint(0, 150),
                    "new_patient_starts": random.randint(0, 30),
                    "market_share_pct": round(random.uniform(0, 0.45), 3),
                    "source_system": "RX_FEED",
                })

    return pd.DataFrame(records)


def generate_patient_support_cases(hcp_df):
    """Generate de-identified patient support case data (aggregate level only)."""
    records = []
    hcp_ids = random.sample(hcp_df["hcp_id"].tolist(), min(800, len(hcp_df)))
    end_date = datetime(2024, 6, 30)
    start_date = datetime(2022, 1, 1)

    for _ in range(N_PATIENT_CASES):
        hcp_id = random.choice(hcp_ids)
        records.append({
            "case_id": f"PSP_{len(records)+1:07d}",
            "hcp_id": hcp_id,
            "product": random.choice(PRODUCTS),
            "case_type": random.choice(["Copay Assistance", "Free Drug", "Adherence Support", "Insurance Navigation"]),
            "case_date": random_date(start_date, end_date).strftime("%Y-%m-%d"),
            "case_status": random.choice(["Open", "Closed", "Escalated"]),
            "resolution_days": random.randint(1, 90) if random.random() > 0.2 else None,
            # No patient-level details — only program-level flags
            "patient_age_band": random.choice(["18-35", "36-50", "51-65", "65+"]),
            "payer_type": random.choice(["Commercial", "Medicare", "Medicaid", "Self-Pay"]),
        })

    return pd.DataFrame(records)


def generate_trial_sites(hco_df):
    """Generate clinical trial site performance data."""
    records = []
    hco_ids = random.sample(hco_df["hco_id"].tolist(), N_TRIAL_SITES)

    for hco_id in hco_ids:
        records.append({
            "site_id": f"SITE_{len(records)+1:04d}",
            "hco_id": hco_id,
            "trial_id": f"TRIAL_{random.randint(1, 15):03d}",
            "activation_date": random_date(datetime(2020, 1, 1), datetime(2022, 12, 31)).strftime("%Y-%m-%d"),
            "enrolled_patients": random.randint(0, 45),
            "screen_failures": random.randint(0, 20),
            "query_rate": round(random.uniform(0, 0.25), 3),
            "protocol_deviations": random.randint(0, 8),
            "site_rating": random.choice(["Excellent", "Good", "Acceptable", "Poor"]),
            "country": "US",
            "pi_hcp_id": f"HCP_{random.randint(1, N_HCPS):05d}",
            "is_active": random.random() > 0.15,
        })

    return pd.DataFrame(records)


def generate_territory_assignments(hcp_df):
    """Generate territory assignment data."""
    records = []
    for _, hcp in hcp_df.iterrows():
        records.append({
            "assignment_id": f"ASGN_{len(records)+1:06d}",
            "hcp_id": hcp["hcp_id"],
            "territory_id": hcp["territory_id"],
            "rep_id": f"REP_{random.randint(1, 200):04d}",
            "assignment_start": random_date(datetime(2022, 1, 1), datetime(2023, 6, 30)).strftime("%Y-%m-%d"),
            "assignment_end": None,
            "is_current": True,
        })

    return pd.DataFrame(records)


def main():
    print("Generating Healthcare synthetic datasets...")

    hcp_df = generate_hcp_master()
    hco_df = generate_hco_master()
    aff_df = generate_hcp_hco_affiliations(hcp_df, hco_df)
    int_df = generate_interactions(hcp_df)
    rx_df = generate_rx_aggregates(hcp_df)
    psp_df = generate_patient_support_cases(hcp_df)
    trial_df = generate_trial_sites(hco_df)
    terr_df = generate_territory_assignments(hcp_df)

    datasets = {
        "hcp_master.csv": hcp_df,
        "hco_master.csv": hco_df,
        "hcp_hco_affiliations.csv": aff_df,
        "hcp_interactions.csv": int_df,
        "rx_aggregates.csv": rx_df,
        "patient_support_cases.csv": psp_df,
        "trial_sites.csv": trial_df,
        "territory_assignments.csv": terr_df,
    }

    for filename, df in datasets.items():
        path = RAW_DIR / filename
        df.to_csv(path, index=False)
        print(f"  ✓ {filename}: {len(df):,} records → {path}")

    print(f"\nAll synthetic data generated in: {RAW_DIR}")


if __name__ == "__main__":
    main()
