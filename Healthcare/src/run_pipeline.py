"""
Healthcare Data Pipeline
Orchestrates: Bronze ingestion → Silver standardization → Gold data products
"""

import os
import json
import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
BRONZE_DIR = BASE_DIR / "data" / "bronze"
SILVER_DIR = BASE_DIR / "data" / "silver"
GOLD_DIR = BASE_DIR / "data" / "gold"
DB_PATH = BASE_DIR / "healthcare.duckdb"

for d in [BRONZE_DIR, SILVER_DIR, GOLD_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def get_connection():
    return duckdb.connect(str(DB_PATH))


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ── Bronze Layer ───────────────────────────────────────────────────────────────

def ingest_bronze(con):
    """Load raw CSVs into Bronze DuckDB tables with metadata."""
    log("=== BRONZE LAYER: Raw Ingestion ===")
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    load_ts = datetime.now().isoformat()

    sources = {
        "bronze_hcp_master": "hcp_master.csv",
        "bronze_hco_master": "hco_master.csv",
        "bronze_hcp_hco_affiliations": "hcp_hco_affiliations.csv",
        "bronze_hcp_interactions": "hcp_interactions.csv",
        "bronze_rx_aggregates": "rx_aggregates.csv",
        "bronze_patient_support": "patient_support_cases.csv",
        "bronze_trial_sites": "trial_sites.csv",
        "bronze_territory_assignments": "territory_assignments.csv",
    }

    for table_name, filename in sources.items():
        path = RAW_DIR / filename
        if not path.exists():
            log(f"  WARNING: {filename} not found — skipping. Run generate_synthetic_data.py first.")
            continue

        df = pd.read_csv(path)
        df["_batch_id"] = batch_id
        df["_load_ts"] = load_ts
        df["_source_file"] = filename
        df["_source_system"] = filename.split("_")[0].upper()

        con.execute(f"DROP TABLE IF EXISTS {table_name}")
        con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
        df.to_parquet(BRONZE_DIR / f"{table_name}.parquet", index=False)
        log(f"  ✓ {table_name}: {len(df):,} rows")

    log(f"Bronze ingestion complete. Batch: {batch_id}")


# ── Silver Layer ───────────────────────────────────────────────────────────────

def transform_silver(con):
    """Standardize, validate, and deduplicate Bronze data into Silver tables."""
    log("\n=== SILVER LAYER: Standardization & Quality ===")

    # silver_hcp_standardized: clean and normalize HCP master
    con.execute("""
        CREATE OR REPLACE TABLE silver_hcp_standardized AS
        SELECT
            hcp_id,
            TRIM(npi)                                   AS npi,
            UPPER(TRIM(first_name))                     AS first_name,
            UPPER(TRIM(last_name))                      AS last_name,
            TRIM(full_name)                             AS full_name,
            UPPER(TRIM(specialty_code))                 AS specialty_code,
            TRIM(specialty_name)                        AS specialty_name,
            specialty_tier,
            UPPER(TRIM(state))                          AS state,
            territory_id,
            degree,
            CAST(years_in_practice AS INTEGER)          AS years_in_practice,
            CAST(is_key_opinion_leader AS BOOLEAN)      AS is_kol,
            CAST(is_investigator AS BOOLEAN)            AS is_investigator,
            CAST(created_date AS DATE)                  AS created_date,
            CAST(updated_date AS DATE)                  AS updated_date,
            -- Data quality flags
            CASE WHEN npi IS NULL OR LENGTH(TRIM(npi)) != 10 THEN 0 ELSE 1 END  AS dq_npi_valid,
            CASE WHEN first_name IS NULL OR first_name = '' THEN 0 ELSE 1 END   AS dq_name_complete,
            CASE WHEN specialty_code IS NULL THEN 0 ELSE 1 END                  AS dq_specialty_present,
            _batch_id,
            _load_ts
        FROM bronze_hcp_master
        WHERE hcp_id IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (PARTITION BY hcp_id ORDER BY _load_ts DESC) = 1
    """)
    count = con.execute("SELECT COUNT(*) FROM silver_hcp_standardized").fetchone()[0]
    log(f"  ✓ silver_hcp_standardized: {count:,} rows")

    # silver_hco_standardized
    con.execute("""
        CREATE OR REPLACE TABLE silver_hco_standardized AS
        SELECT
            hco_id,
            TRIM(hco_name)          AS hco_name,
            TRIM(hco_type)          AS hco_type,
            UPPER(TRIM(state))      AS state,
            TRIM(city)              AS city,
            CAST(bed_count AS INTEGER) AS bed_count,
            CAST(is_teaching AS BOOLEAN)      AS is_teaching,
            CAST(is_nci_designated AS BOOLEAN) AS is_nci_designated,
            CAST(created_date AS DATE)        AS created_date,
            _batch_id,
            _load_ts
        FROM bronze_hco_master
        WHERE hco_id IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (PARTITION BY hco_id ORDER BY _load_ts DESC) = 1
    """)
    count = con.execute("SELECT COUNT(*) FROM silver_hco_standardized").fetchone()[0]
    log(f"  ✓ silver_hco_standardized: {count:,} rows")

    # silver_hcp_hco_affiliations
    con.execute("""
        CREATE OR REPLACE TABLE silver_hcp_hco_affiliations AS
        SELECT
            affiliation_id,
            hcp_id,
            hco_id,
            affiliation_type,
            CAST(is_primary AS BOOLEAN)   AS is_primary,
            CAST(start_date AS DATE)       AS start_date
        FROM bronze_hcp_hco_affiliations
        WHERE hcp_id IS NOT NULL AND hco_id IS NOT NULL
    """)
    count = con.execute("SELECT COUNT(*) FROM silver_hcp_hco_affiliations").fetchone()[0]
    log(f"  ✓ silver_hcp_hco_affiliations: {count:,} rows")

    # silver_interactions_clean: validated interaction data
    con.execute("""
        CREATE OR REPLACE TABLE silver_interactions_clean AS
        SELECT
            interaction_id,
            hcp_id,
            rep_id,
            product,
            interaction_type,
            CAST(interaction_date AS DATE)          AS interaction_date,
            CAST(duration_minutes AS INTEGER)       AS duration_minutes,
            outcome,
            CAST(samples_dropped AS INTEGER)        AS samples_dropped,
            source_system,
            -- Quality: only keep interactions with valid dates
            CASE WHEN interaction_date <= CURRENT_DATE THEN 1 ELSE 0 END AS dq_date_valid
        FROM bronze_hcp_interactions
        WHERE hcp_id IS NOT NULL
          AND interaction_date IS NOT NULL
          AND CAST(interaction_date AS DATE) <= CURRENT_DATE
    """)
    count = con.execute("SELECT COUNT(*) FROM silver_interactions_clean").fetchone()[0]
    log(f"  ✓ silver_interactions_clean: {count:,} rows")

    # silver_rx_aggregates
    con.execute("""
        CREATE OR REPLACE TABLE silver_rx_aggregates AS
        SELECT
            rx_id,
            hcp_id,
            product,
            CAST(period_month AS INTEGER)               AS period_month,
            CAST(period_year AS INTEGER)                AS period_year,
            CAST(total_rx_count AS INTEGER)             AS total_rx_count,
            CAST(new_patient_starts AS INTEGER)         AS new_patient_starts,
            CAST(market_share_pct AS DOUBLE)            AS market_share_pct,
            source_system
        FROM bronze_rx_aggregates
        WHERE hcp_id IS NOT NULL
          AND total_rx_count >= 0
    """)
    count = con.execute("SELECT COUNT(*) FROM silver_rx_aggregates").fetchone()[0]
    log(f"  ✓ silver_rx_aggregates: {count:,} rows")

    # silver_patient_support_agg: strip any individual-level details, aggregate
    con.execute("""
        CREATE OR REPLACE TABLE silver_patient_support_agg AS
        SELECT
            hcp_id,
            product,
            case_type,
            payer_type,
            DATE_TRUNC('month', CAST(case_date AS DATE)) AS case_month,
            COUNT(*) AS case_count,
            AVG(CAST(resolution_days AS DOUBLE)) AS avg_resolution_days,
            SUM(CASE WHEN case_status = 'Escalated' THEN 1 ELSE 0 END) AS escalated_count
        FROM bronze_patient_support
        WHERE hcp_id IS NOT NULL
        GROUP BY hcp_id, product, case_type, payer_type, DATE_TRUNC('month', CAST(case_date AS DATE))
    """)
    count = con.execute("SELECT COUNT(*) FROM silver_patient_support_agg").fetchone()[0]
    log(f"  ✓ silver_patient_support_agg: {count:,} rows")

    # silver_trial_sites_clean
    con.execute("""
        CREATE OR REPLACE TABLE silver_trial_sites_clean AS
        SELECT
            site_id,
            hco_id,
            trial_id,
            CAST(activation_date AS DATE)       AS activation_date,
            CAST(enrolled_patients AS INTEGER)  AS enrolled_patients,
            CAST(screen_failures AS INTEGER)    AS screen_failures,
            CAST(query_rate AS DOUBLE)          AS query_rate,
            CAST(protocol_deviations AS INTEGER) AS protocol_deviations,
            site_rating,
            country,
            pi_hcp_id,
            CAST(is_active AS BOOLEAN)          AS is_active
        FROM bronze_trial_sites
        WHERE site_id IS NOT NULL
    """)
    count = con.execute("SELECT COUNT(*) FROM silver_trial_sites_clean").fetchone()[0]
    log(f"  ✓ silver_trial_sites_clean: {count:,} rows")

    log("Silver transformation complete.")


# ── Gold Layer ─────────────────────────────────────────────────────────────────

def build_gold(con):
    """Build Gold data products: HCP 360, targeting score, PSP summary, trial site priority."""
    log("\n=== GOLD LAYER: Data Products ===")

    # gold_hcp_360: Golden HCP record with aggregated signals
    con.execute("""
        CREATE OR REPLACE TABLE gold_hcp_360 AS
        WITH interaction_agg AS (
            SELECT
                hcp_id,
                COUNT(*) AS total_interactions_12m,
                COUNT(CASE WHEN interaction_date >= CURRENT_DATE - INTERVAL '90 days' THEN 1 END)
                    AS interactions_90d,
                MAX(interaction_date) AS last_interaction_date,
                COUNT(CASE WHEN outcome = 'Positive' THEN 1 END) AS positive_outcomes,
                SUM(samples_dropped) AS total_samples_dropped
            FROM silver_interactions_clean
            WHERE interaction_date >= CURRENT_DATE - INTERVAL '365 days'
            GROUP BY hcp_id
        ),
        rx_agg AS (
            SELECT
                hcp_id,
                SUM(total_rx_count) AS total_rx_12m,
                SUM(new_patient_starts) AS total_new_starts_12m,
                AVG(market_share_pct) AS avg_market_share
            FROM silver_rx_aggregates
            WHERE period_year >= EXTRACT(YEAR FROM CURRENT_DATE) - 1
            GROUP BY hcp_id
        ),
        psp_agg AS (
            SELECT
                hcp_id,
                SUM(case_count) AS total_psp_cases,
                SUM(escalated_count) AS total_psp_escalations
            FROM silver_patient_support_agg
            GROUP BY hcp_id
        )
        SELECT
            h.hcp_id,
            h.npi,
            h.first_name,
            h.last_name,
            h.full_name,
            h.specialty_code,
            h.specialty_name,
            h.specialty_tier,
            h.state,
            h.territory_id,
            h.degree,
            h.years_in_practice,
            h.is_kol,
            h.is_investigator,
            -- Interaction signals
            COALESCE(i.total_interactions_12m, 0) AS total_interactions_12m,
            COALESCE(i.interactions_90d, 0)        AS interactions_90d,
            i.last_interaction_date,
            COALESCE(i.positive_outcomes, 0)       AS positive_outcomes,
            -- Prescription signals
            COALESCE(r.total_rx_12m, 0)            AS total_rx_12m,
            COALESCE(r.total_new_starts_12m, 0)    AS total_new_starts_12m,
            COALESCE(r.avg_market_share, 0)        AS avg_market_share,
            -- Patient support signals
            COALESCE(p.total_psp_cases, 0)         AS total_psp_cases,
            COALESCE(p.total_psp_escalations, 0)   AS total_psp_escalations,
            -- Engagement score: composite signal (0-100)
            LEAST(100, GREATEST(0,
                COALESCE(i.interactions_90d, 0) * 8 +
                COALESCE(i.positive_outcomes, 0) * 5 +
                CASE h.specialty_tier WHEN 'A' THEN 20 WHEN 'B' THEN 15 WHEN 'C' THEN 10 ELSE 5 END +
                CASE WHEN h.is_kol THEN 15 ELSE 0 END
            )) AS engagement_score,
            h.dq_npi_valid,
            h.dq_name_complete,
            CURRENT_TIMESTAMP AS gold_created_ts
        FROM silver_hcp_standardized h
        LEFT JOIN interaction_agg i USING (hcp_id)
        LEFT JOIN rx_agg r USING (hcp_id)
        LEFT JOIN psp_agg p USING (hcp_id)
    """)
    count = con.execute("SELECT COUNT(*) FROM gold_hcp_360").fetchone()[0]
    log(f"  ✓ gold_hcp_360: {count:,} rows")

    # gold_hcp_targeting_score: AI-ready feature set with targeting tier
    con.execute("""
        CREATE OR REPLACE TABLE gold_hcp_targeting_score AS
        SELECT
            hcp_id,
            npi,
            specialty_tier,
            territory_id,
            state,
            total_interactions_12m,
            interactions_90d,
            CASE WHEN last_interaction_date IS NULL THEN 999
                 ELSE DATEDIFF('day', last_interaction_date, CURRENT_DATE)
            END AS days_since_last_interaction,
            positive_outcomes,
            total_rx_12m,
            total_new_starts_12m,
            ROUND(avg_market_share * 100, 2) AS market_share_pct,
            total_psp_cases,
            engagement_score,
            CAST(is_kol AS INTEGER)          AS is_kol_flag,
            CAST(is_investigator AS INTEGER)  AS is_investigator_flag,
            years_in_practice,
            -- Targeting priority: rule-based label for supervised learning
            CASE
                WHEN specialty_tier = 'A' AND engagement_score >= 60 AND total_rx_12m >= 50 THEN 'A'
                WHEN specialty_tier IN ('A','B') AND engagement_score >= 40 THEN 'B'
                WHEN engagement_score >= 20 OR total_rx_12m >= 20 THEN 'C'
                ELSE 'D'
            END AS targeting_priority,
            CURRENT_TIMESTAMP AS feature_ts
        FROM gold_hcp_360
    """)
    count = con.execute("SELECT COUNT(*) FROM gold_hcp_targeting_score").fetchone()[0]
    log(f"  ✓ gold_hcp_targeting_score: {count:,} rows")

    # gold_patient_support_summary: privacy-safe territory-level aggregates
    con.execute("""
        CREATE OR REPLACE TABLE gold_patient_support_summary AS
        SELECT
            h.territory_id,
            p.product,
            p.case_type,
            DATE_TRUNC('quarter', p.case_month)  AS case_quarter,
            SUM(p.case_count)                    AS total_cases,
            AVG(p.avg_resolution_days)           AS avg_resolution_days,
            SUM(p.escalated_count)               AS total_escalations,
            ROUND(SUM(p.escalated_count)::DOUBLE / NULLIF(SUM(p.case_count), 0) * 100, 2)
                AS escalation_rate_pct
        FROM silver_patient_support_agg p
        JOIN silver_hcp_standardized h USING (hcp_id)
        GROUP BY h.territory_id, p.product, p.case_type, DATE_TRUNC('quarter', p.case_month)
    """)
    count = con.execute("SELECT COUNT(*) FROM gold_patient_support_summary").fetchone()[0]
    log(f"  ✓ gold_patient_support_summary: {count:,} rows")

    # gold_trial_site_priority: site scoring for clinical trial prioritization
    con.execute("""
        CREATE OR REPLACE TABLE gold_trial_site_priority AS
        SELECT
            s.site_id,
            s.hco_id,
            o.hco_name,
            o.state,
            s.trial_id,
            s.enrolled_patients,
            s.screen_failures,
            s.query_rate,
            s.protocol_deviations,
            s.site_rating,
            s.is_active,
            o.is_teaching,
            o.is_nci_designated,
            -- Enrollment success rate
            ROUND(s.enrolled_patients::DOUBLE /
                  NULLIF(s.enrolled_patients + s.screen_failures, 0) * 100, 2) AS enrollment_success_pct,
            -- Site quality score (0-100)
            LEAST(100, GREATEST(0,
                s.enrolled_patients * 2 +
                CASE s.site_rating
                    WHEN 'Excellent' THEN 30
                    WHEN 'Good' THEN 20
                    WHEN 'Acceptable' THEN 10
                    ELSE 0
                END -
                s.protocol_deviations * 5 -
                ROUND(s.query_rate * 100)
            )) AS site_quality_score,
            -- Priority tier
            CASE
                WHEN s.enrolled_patients >= 30 AND s.site_rating IN ('Excellent','Good') THEN 'HIGH'
                WHEN s.enrolled_patients >= 15 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS priority_tier,
            CURRENT_TIMESTAMP AS gold_created_ts
        FROM silver_trial_sites_clean s
        JOIN silver_hco_standardized o USING (hco_id)
    """)
    count = con.execute("SELECT COUNT(*) FROM gold_trial_site_priority").fetchone()[0]
    log(f"  ✓ gold_trial_site_priority: {count:,} rows")

    # Export Gold tables to Parquet
    for table in ["gold_hcp_360", "gold_hcp_targeting_score",
                  "gold_patient_support_summary", "gold_trial_site_priority"]:
        df = con.execute(f"SELECT * FROM {table}").df()
        df.to_parquet(GOLD_DIR / f"{table}.parquet", index=False)
        log(f"  → Exported {table}.parquet")

    log("Gold layer complete.")


def main():
    log("Starting Healthcare Data Pipeline")
    con = get_connection()
    try:
        ingest_bronze(con)
        transform_silver(con)
        build_gold(con)
        log("\nPipeline completed successfully.")
        log(f"Database: {DB_PATH}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
