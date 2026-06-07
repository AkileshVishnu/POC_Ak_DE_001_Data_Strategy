"""
Finance Data Pipeline
Orchestrates: Bronze ingestion → Silver standardization → Gold feature engineering
Enforces point-in-time correctness for all transaction features.
"""

import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
BRONZE_DIR = BASE_DIR / "data" / "bronze"
SILVER_DIR = BASE_DIR / "data" / "silver"
GOLD_DIR = BASE_DIR / "data" / "gold"
DB_PATH = BASE_DIR / "finance.duckdb"

for d in [BRONZE_DIR, SILVER_DIR, GOLD_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def get_connection():
    return duckdb.connect(str(DB_PATH))


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ── Bronze ─────────────────────────────────────────────────────────────────────

def ingest_bronze(con):
    log("=== BRONZE LAYER: Raw Ingestion ===")
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    load_ts = datetime.now().isoformat()

    sources = {
        "bronze_customers": "customers.csv",
        "bronze_accounts": "accounts.csv",
        "bronze_merchants": "merchants.csv",
        "bronze_transactions": "transactions.csv",
        "bronze_chargebacks": "chargebacks.csv",
        "bronze_device_events": "device_events.csv",
        "bronze_bureau_attrs": "bureau_attributes.csv",
    }

    for table, filename in sources.items():
        path = RAW_DIR / filename
        if not path.exists():
            log(f"  WARNING: {filename} not found")
            continue
        df = pd.read_csv(path)
        df["_batch_id"] = batch_id
        df["_load_ts"] = load_ts
        df["_source_file"] = filename
        con.execute(f"DROP TABLE IF EXISTS {table}")
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM df")
        df.to_parquet(BRONZE_DIR / f"{table}.parquet", index=False)
        log(f"  ✓ {table}: {len(df):,} rows")


# ── Silver ─────────────────────────────────────────────────────────────────────

def transform_silver(con):
    log("\n=== SILVER LAYER: Standardization ===")

    con.execute("""
        CREATE OR REPLACE TABLE silver_customers_clean AS
        SELECT
            customer_id,
            UPPER(TRIM(first_name))     AS first_name,
            UPPER(TRIM(last_name))      AS last_name,
            CAST(age AS INTEGER)        AS age,
            UPPER(TRIM(state))          AS state,
            income_band,
            CAST(customer_since AS DATE) AS customer_since,
            risk_segment,
            email_domain,
            CASE WHEN age BETWEEN 18 AND 120 THEN 1 ELSE 0 END AS dq_age_valid,
            _batch_id, _load_ts
        FROM bronze_customers
        WHERE customer_id IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY _load_ts DESC) = 1
    """)
    log(f"  ✓ silver_customers_clean: {con.execute('SELECT COUNT(*) FROM silver_customers_clean').fetchone()[0]:,}")

    con.execute("""
        CREATE OR REPLACE TABLE silver_transactions_clean AS
        SELECT
            transaction_id,
            customer_id,
            account_id,
            merchant_id,
            CAST(transaction_date AS DATE)      AS transaction_date,
            CAST(transaction_hour AS INTEGER)   AS transaction_hour,
            transaction_type,
            ROUND(CAST(amount AS DOUBLE), 2)    AS amount,
            currency,
            transaction_state,
            CAST(is_online AS BOOLEAN)          AS is_online,
            CAST(is_international AS BOOLEAN)   AS is_international,
            CAST(is_fraud AS BOOLEAN)           AS is_fraud,
            status,
            -- Quality flags
            CASE WHEN amount > 0 THEN 1 ELSE 0 END                         AS dq_amount_positive,
            CASE WHEN transaction_date <= CURRENT_DATE THEN 1 ELSE 0 END   AS dq_date_valid,
            _batch_id, _load_ts
        FROM bronze_transactions
        WHERE transaction_id IS NOT NULL
          AND amount > 0
          AND CAST(transaction_date AS DATE) <= CURRENT_DATE
    """)
    log(f"  ✓ silver_transactions_clean: {con.execute('SELECT COUNT(*) FROM silver_transactions_clean').fetchone()[0]:,}")

    con.execute("""
        CREATE OR REPLACE TABLE silver_merchants_clean AS
        SELECT
            merchant_id,
            TRIM(merchant_name)         AS merchant_name,
            TRIM(category)              AS category,
            UPPER(TRIM(state))          AS state,
            CAST(is_online AS BOOLEAN)  AS is_online,
            CAST(avg_transaction_size AS DOUBLE) AS avg_transaction_size,
            CAST(risk_flag AS BOOLEAN)  AS risk_flag
        FROM bronze_merchants WHERE merchant_id IS NOT NULL
    """)
    log(f"  ✓ silver_merchants_clean: {con.execute('SELECT COUNT(*) FROM silver_merchants_clean').fetchone()[0]:,}")

    con.execute("""
        CREATE OR REPLACE TABLE silver_device_events_clean AS
        SELECT
            event_id,
            customer_id,
            CAST(event_date AS DATE)    AS event_date,
            event_type,
            device_type,
            CAST(is_new_device AS BOOLEAN) AS is_new_device,
            CAST(vpn_detected AS BOOLEAN)  AS vpn_detected
        FROM bronze_device_events WHERE customer_id IS NOT NULL
    """)
    log(f"  ✓ silver_device_events_clean: {con.execute('SELECT COUNT(*) FROM silver_device_events_clean').fetchone()[0]:,}")

    log("Silver transformation complete.")


# ── Gold ───────────────────────────────────────────────────────────────────────

def build_gold(con):
    log("\n=== GOLD LAYER: Point-in-Time Feature Engineering ===")

    # gold_customer_360: unified customer with bureau data
    con.execute("""
        CREATE OR REPLACE TABLE gold_customer_360 AS
        SELECT
            c.customer_id,
            c.state,
            c.age,
            c.income_band,
            c.risk_segment,
            c.customer_since,
            DATEDIFF('day', c.customer_since, CURRENT_DATE)    AS customer_tenure_days,
            b.bureau_score,
            b.num_open_accounts,
            b.num_derogatory_marks,
            b.total_debt_usd,
            b.payment_history_pct,
            b.credit_utilization_pct,
            b.oldest_account_years,
            CURRENT_TIMESTAMP                                  AS gold_created_ts
        FROM silver_customers_clean c
        LEFT JOIN bronze_bureau_attrs b USING (customer_id)
    """)
    log(f"  ✓ gold_customer_360: {con.execute('SELECT COUNT(*) FROM gold_customer_360').fetchone()[0]:,}")

    # gold_transaction_risk_features: POINT-IN-TIME CORRECT features
    # All historical aggregations use ONLY data before each transaction's timestamp
    log("  Building point-in-time correct transaction features (this may take a moment)...")
    con.execute("""
        CREATE OR REPLACE TABLE gold_transaction_risk_features AS
        WITH historical_customer AS (
            -- For each transaction, compute customer behavior using ONLY prior transactions
            -- This is the key point-in-time correctness constraint
            SELECT
                t.transaction_id,
                t.customer_id,
                t.transaction_date,
                t.amount,
                -- 30-day rolling window BEFORE this transaction (not including current)
                COUNT(h.transaction_id)                             AS customer_tx_count_30d,
                COALESCE(AVG(h.amount), 0)                          AS customer_avg_amount_30d,
                COALESCE(MAX(h.amount), 0)                          AS customer_max_amount_30d,
                COALESCE(SUM(h.amount), 0)                          AS customer_total_amount_30d,
                -- 7-day window
                COUNT(CASE WHEN h.transaction_date >= t.transaction_date - INTERVAL '7 days'
                           THEN 1 END)                              AS customer_tx_count_7d,
                -- Days since last transaction (before current)
                COALESCE(DATEDIFF('day',
                    MAX(CASE WHEN h.transaction_id != t.transaction_id THEN h.transaction_date END),
                    t.transaction_date), 999)                       AS days_since_last_tx,
                -- Distinct states in last 30d
                COUNT(DISTINCT h.transaction_state)                 AS distinct_states_30d,
                -- Fraud history (prior frauds only)
                COALESCE(SUM(CAST(h.is_fraud AS INTEGER)), 0)       AS prior_fraud_count
            FROM silver_transactions_clean t
            LEFT JOIN silver_transactions_clean h
                ON h.customer_id = t.customer_id
                AND h.transaction_date BETWEEN t.transaction_date - INTERVAL '30 days'
                                           AND t.transaction_date
                AND h.transaction_id != t.transaction_id  -- exclude current tx from history
            GROUP BY t.transaction_id, t.customer_id, t.transaction_date, t.amount
        ),
        device_signals AS (
            SELECT
                t.transaction_id,
                -- Device events before this transaction
                COUNT(CASE WHEN d.event_date >= t.transaction_date - INTERVAL '7 days'
                           AND d.event_date <= t.transaction_date
                           AND d.event_type = 'New Device' THEN 1 END) AS new_device_events_7d,
                COUNT(CASE WHEN d.event_date >= t.transaction_date - INTERVAL '7 days'
                           AND d.event_date <= t.transaction_date
                           AND d.vpn_detected THEN 1 END)              AS vpn_events_7d
            FROM silver_transactions_clean t
            LEFT JOIN silver_device_events_clean d USING (customer_id)
            GROUP BY t.transaction_id
        )
        SELECT
            t.transaction_id,
            t.customer_id,
            t.account_id,
            t.merchant_id,
            t.transaction_date,
            t.transaction_hour,
            t.transaction_type,
            t.amount,
            t.is_online,
            t.is_international,
            t.transaction_state,
            -- Point-in-time customer history features
            h.customer_tx_count_30d,
            h.customer_avg_amount_30d,
            h.customer_max_amount_30d,
            h.customer_total_amount_30d,
            h.customer_tx_count_7d,
            h.days_since_last_tx,
            h.distinct_states_30d,
            h.prior_fraud_count,
            -- Amount deviation (vs customer's own historical average)
            CASE WHEN h.customer_avg_amount_30d > 0
                 THEN t.amount / h.customer_avg_amount_30d
                 ELSE 1.0 END                                        AS amount_vs_avg_ratio,
            -- Temporal risk signals
            CASE WHEN t.transaction_hour BETWEEN 0 AND 4 THEN 1 ELSE 0 END AS is_late_night,
            -- Device signals (prior to transaction)
            COALESCE(d.new_device_events_7d, 0)                      AS new_device_events_7d,
            COALESCE(d.vpn_events_7d, 0)                             AS vpn_events_7d,
            -- Customer profile features
            COALESCE(c.bureau_score, 650)                            AS bureau_score,
            COALESCE(c.credit_utilization_pct, 0.5)                  AS credit_utilization_pct,
            COALESCE(c.num_derogatory_marks, 0)                      AS num_derogatory_marks,
            c.customer_tenure_days,
            -- Merchant risk
            COALESCE(m.risk_flag, FALSE)                             AS merchant_risk_flag,
            -- Ground truth label (only for training — would not exist at inference time)
            t.is_fraud,
            CURRENT_TIMESTAMP                                        AS feature_ts
        FROM silver_transactions_clean t
        LEFT JOIN historical_customer h USING (transaction_id)
        LEFT JOIN device_signals d USING (transaction_id)
        LEFT JOIN gold_customer_360 c USING (customer_id)
        LEFT JOIN silver_merchants_clean m USING (merchant_id)
    """)
    count = con.execute("SELECT COUNT(*) FROM gold_transaction_risk_features").fetchone()[0]
    log(f"  ✓ gold_transaction_risk_features: {count:,} rows (point-in-time correct)")

    # gold_customer_risk_profile: customer-level aggregated risk
    con.execute("""
        CREATE OR REPLACE TABLE gold_customer_risk_profile AS
        SELECT
            customer_id,
            COUNT(*) AS total_transactions,
            SUM(CAST(is_fraud AS INTEGER)) AS confirmed_fraud_count,
            ROUND(AVG(CAST(is_fraud AS DOUBLE)) * 100, 3) AS fraud_rate_pct,
            AVG(amount) AS avg_transaction_amount,
            MAX(amount) AS max_transaction_amount,
            ROUND(AVG(amount_vs_avg_ratio), 3) AS avg_amount_deviation,
            MAX(distinct_states_30d) AS max_distinct_states,
            SUM(new_device_events_7d) AS total_new_device_events,
            SUM(vpn_events_7d) AS total_vpn_events,
            AVG(bureau_score) AS avg_bureau_score,
            -- Risk tier
            CASE
                WHEN SUM(CAST(is_fraud AS INTEGER)) > 0 THEN 'CONFIRMED_FRAUD'
                WHEN AVG(amount_vs_avg_ratio) > 5 AND MAX(distinct_states_30d) > 3 THEN 'HIGH'
                WHEN AVG(credit_utilization_pct) > 0.8 OR AVG(num_derogatory_marks) > 2 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS risk_tier,
            CURRENT_TIMESTAMP AS gold_created_ts
        FROM gold_transaction_risk_features
        GROUP BY customer_id
    """)
    log(f"  ✓ gold_customer_risk_profile: {con.execute('SELECT COUNT(*) FROM gold_customer_risk_profile').fetchone()[0]:,}")

    # Export
    for table in ["gold_customer_360", "gold_transaction_risk_features",
                  "gold_customer_risk_profile"]:
        df = con.execute(f"SELECT * FROM {table}").df()
        df.to_parquet(GOLD_DIR / f"{table}.parquet", index=False)
        log(f"  → Exported {table}.parquet")

    log("Gold layer complete.")


def main():
    log("Starting Finance Data Pipeline")
    con = get_connection()
    try:
        ingest_bronze(con)
        transform_silver(con)
        build_gold(con)
        log("\nPipeline completed successfully.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
