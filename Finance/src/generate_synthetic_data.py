"""
Finance Synthetic Data Generator
Generates realistic synthetic financial datasets for fraud detection POC.
Includes realistic fraud patterns and temporal structure.
No real financial, PII, or account data is used.
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

N_CUSTOMERS = 5000
N_MERCHANTS = 2000
N_TRANSACTIONS = 100000
FRAUD_RATE = 0.03

STATES = ["CA", "TX", "FL", "NY", "PA", "OH", "IL", "GA", "NC", "MI",
          "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI"]
MERCHANT_CATS = ["Grocery", "Gas Station", "Restaurant", "Online Retail", "Travel",
                 "Electronics", "Healthcare", "Entertainment", "ATM", "Utilities"]
TX_TYPES = ["Purchase", "ATM Withdrawal", "Online Payment", "Recurring", "Transfer"]
RISK_SEGMENTS = ["Low", "Medium", "High"]


def random_date(start, end):
    return start + timedelta(days=random.randint(0, (end - start).days))


def generate_customers():
    records = []
    first_names = ["James", "Maria", "John", "Linda", "Robert", "Barbara", "Michael",
                   "Susan", "William", "Jessica", "David", "Sarah", "Richard", "Karen"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
                  "Davis", "Wilson", "Anderson", "Taylor", "Thomas", "Jackson", "White"]

    for i in range(N_CUSTOMERS):
        age = random.randint(21, 80)
        income_band = (
            "Low" if age < 30 else
            random.choice(["Low", "Medium"]) if age < 40 else
            random.choice(["Medium", "High"])
        )
        records.append({
            "customer_id": f"CUST_{i+1:06d}",
            "first_name": random.choice(first_names),
            "last_name": random.choice(last_names),
            "age": age,
            "state": random.choice(STATES),
            "income_band": income_band,
            "customer_since": random_date(datetime(2010, 1, 1), datetime(2022, 12, 31)).strftime("%Y-%m-%d"),
            "risk_segment": random.choice(RISK_SEGMENTS),
            "email_domain": random.choice(["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]),
            "phone_area_code": random.randint(200, 999),
        })
    return pd.DataFrame(records)


def generate_accounts(customers_df):
    records = []
    for _, c in customers_df.iterrows():
        n_accts = np.random.choice([1, 2, 3], p=[0.6, 0.3, 0.1])
        for j in range(n_accts):
            records.append({
                "account_id": f"ACCT_{len(records)+1:07d}",
                "customer_id": c["customer_id"],
                "account_type": random.choice(["Checking", "Savings", "Credit"]),
                "open_date": c["customer_since"],
                "credit_limit": random.choice([1000, 2500, 5000, 10000, 25000]) if j == 0 else None,
                "is_primary": j == 0,
                "status": random.choice(["Active", "Active", "Active", "Suspended"]),
            })
    return pd.DataFrame(records)


def generate_merchants():
    records = []
    for i in range(N_MERCHANTS):
        cat = random.choice(MERCHANT_CATS)
        records.append({
            "merchant_id": f"MER_{i+1:05d}",
            "merchant_name": f"{cat} Store {i+1}",
            "category": cat,
            "state": random.choice(STATES),
            "is_online": cat in ["Online Retail", "Entertainment"],
            "avg_transaction_size": round(random.uniform(5, 500), 2),
            "risk_flag": random.random() < 0.05,
        })
    return pd.DataFrame(records)


def generate_transactions(customers_df, accounts_df, merchants_df):
    """Generate transactions with realistic fraud patterns."""
    records = []
    accounts = accounts_df.groupby("customer_id")["account_id"].apply(list).to_dict()
    merchant_ids = merchants_df["merchant_id"].tolist()
    customer_ids = customers_df["customer_id"].tolist()
    start_date = datetime(2022, 1, 1)
    end_date = datetime(2024, 6, 30)

    for i in range(N_TRANSACTIONS):
        cust_id = random.choice(customer_ids)
        acct_id = random.choice(accounts.get(cust_id, ["ACCT_UNKNOWN"]))
        tx_date = random_date(start_date, end_date)
        is_fraud = random.random() < FRAUD_RATE

        if is_fraud:
            # Fraud patterns: unusual amounts, different state, late night
            amount = round(random.uniform(200, 5000), 2)
            hour = random.choice([0, 1, 2, 3, 23])
            tx_state = random.choice([s for s in STATES])
        else:
            amount = round(random.expovariate(1 / 85), 2)  # typical spend
            amount = min(amount, 2000)
            hour = random.randint(6, 22)
            tx_state = customers_df[customers_df["customer_id"] == cust_id]["state"].values[0]

        merchant_id = random.choice(merchant_ids)
        tx_type = random.choice(TX_TYPES)

        records.append({
            "transaction_id": f"TX_{i+1:08d}",
            "customer_id": cust_id,
            "account_id": acct_id,
            "merchant_id": merchant_id,
            "transaction_date": tx_date.strftime("%Y-%m-%d"),
            "transaction_hour": hour,
            "transaction_type": tx_type,
            "amount": amount,
            "currency": "USD",
            "transaction_state": tx_state,
            "is_online": random.random() < 0.35,
            "is_international": random.random() < 0.02,
            "is_fraud": is_fraud,  # Ground truth label
            "status": "Completed",
        })

    return pd.DataFrame(records)


def generate_chargebacks(transactions_df):
    """Generate chargeback records for labeled fraud transactions."""
    fraud_txs = transactions_df[transactions_df["is_fraud"]].copy()
    records = []
    for _, tx in fraud_txs.iterrows():
        if random.random() < 0.7:  # Not all fraud results in chargeback
            cb_date = datetime.strptime(tx["transaction_date"], "%Y-%m-%d") + timedelta(days=random.randint(7, 60))
            records.append({
                "chargeback_id": f"CB_{len(records)+1:06d}",
                "transaction_id": tx["transaction_id"],
                "customer_id": tx["customer_id"],
                "chargeback_date": cb_date.strftime("%Y-%m-%d"),
                "chargeback_amount": tx["amount"],
                "reason_code": random.choice(["FRAUD", "NOT_RECEIVED", "UNAUTHORIZED", "DUPLICATE"]),
                "status": random.choice(["Resolved", "Pending", "Reversed"]),
            })
    return pd.DataFrame(records)


def generate_device_events(transactions_df):
    """Generate device/login event data."""
    records = []
    customer_ids = transactions_df["customer_id"].unique().tolist()
    start_date = datetime(2022, 1, 1)
    end_date = datetime(2024, 6, 30)

    for cust_id in customer_ids:
        n_events = random.randint(5, 50)
        for _ in range(n_events):
            records.append({
                "event_id": f"DEV_{len(records)+1:08d}",
                "customer_id": cust_id,
                "event_date": random_date(start_date, end_date).strftime("%Y-%m-%d"),
                "event_hour": random.randint(0, 23),
                "event_type": random.choice(["Login", "Password Change", "New Device", "Logout", "Failed Login"]),
                "device_type": random.choice(["Mobile", "Desktop", "Tablet"]),
                "os": random.choice(["iOS", "Android", "Windows", "MacOS"]),
                "is_new_device": random.random() < 0.1,
                "vpn_detected": random.random() < 0.03,
            })

    return pd.DataFrame(records)


def generate_bureau_attributes(customers_df):
    """Generate credit bureau-like attribute data."""
    records = []
    for _, c in customers_df.iterrows():
        records.append({
            "customer_id": c["customer_id"],
            "bureau_score": random.randint(450, 850),
            "num_open_accounts": random.randint(1, 15),
            "num_derogatory_marks": random.randint(0, 5),
            "total_debt_usd": round(random.uniform(0, 150000), 2),
            "payment_history_pct": round(random.uniform(0.6, 1.0), 3),
            "credit_utilization_pct": round(random.uniform(0, 0.95), 3),
            "oldest_account_years": random.randint(1, 25),
            "bureau_pull_date": random_date(datetime(2023, 1, 1), datetime(2024, 3, 31)).strftime("%Y-%m-%d"),
        })
    return pd.DataFrame(records)


def main():
    print("Generating Finance synthetic datasets...")

    customers_df = generate_customers()
    accounts_df = generate_accounts(customers_df)
    merchants_df = generate_merchants()
    transactions_df = generate_transactions(customers_df, accounts_df, merchants_df)
    chargebacks_df = generate_chargebacks(transactions_df)
    device_df = generate_device_events(transactions_df)
    bureau_df = generate_bureau_attributes(customers_df)

    datasets = {
        "customers.csv": customers_df,
        "accounts.csv": accounts_df,
        "merchants.csv": merchants_df,
        "transactions.csv": transactions_df,
        "chargebacks.csv": chargebacks_df,
        "device_events.csv": device_df,
        "bureau_attributes.csv": bureau_df,
    }

    for filename, df in datasets.items():
        path = RAW_DIR / filename
        df.to_csv(path, index=False)
        fraud_note = f"  ({df['is_fraud'].sum()} fraud)" if "is_fraud" in df.columns else ""
        print(f"  ✓ {filename}: {len(df):,} records{fraud_note} → {path}")

    print(f"\nFraud rate: {transactions_df['is_fraud'].mean()*100:.2f}%")
    print(f"All Finance synthetic data generated in: {RAW_DIR}")


if __name__ == "__main__":
    main()
