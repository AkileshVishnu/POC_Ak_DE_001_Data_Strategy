-- Gold HCP 360: Unified golden HCP record (MDM output)
-- Consolidates all signals into a single, governed HCP entity

WITH interaction_signals AS (
    SELECT
        hcp_id,
        COUNT(*)                                                   AS total_interactions_12m,
        COUNT(CASE WHEN interaction_date >= CURRENT_DATE - INTERVAL '90 days' THEN 1 END)
                                                                   AS interactions_90d,
        MAX(interaction_date)                                      AS last_interaction_date,
        SUM(CASE WHEN outcome = 'Positive' THEN 1 ELSE 0 END)     AS positive_outcomes
    FROM {{ ref('silver_interactions_clean') }}
    WHERE interaction_date >= CURRENT_DATE - INTERVAL '365 days'
    GROUP BY 1
),

rx_signals AS (
    SELECT
        hcp_id,
        SUM(total_rx_count)        AS total_rx_12m,
        SUM(new_patient_starts)    AS total_new_starts_12m,
        AVG(market_share_pct)      AS avg_market_share
    FROM {{ ref('silver_rx_aggregates') }}
    WHERE period_year >= EXTRACT(YEAR FROM CURRENT_DATE) - 1
    GROUP BY 1
)

SELECT
    h.hcp_id,
    h.npi,
    h.full_name,
    h.specialty_code,
    h.specialty_name,
    h.specialty_tier,
    h.state,
    h.territory_id,
    h.is_kol,
    h.is_investigator,
    COALESCE(i.total_interactions_12m, 0) AS total_interactions_12m,
    COALESCE(i.interactions_90d, 0)        AS interactions_90d,
    i.last_interaction_date,
    COALESCE(r.total_rx_12m, 0)            AS total_rx_12m,
    COALESCE(r.avg_market_share, 0)        AS avg_market_share,
    LEAST(100, GREATEST(0,
        COALESCE(i.interactions_90d, 0) * 8 +
        COALESCE(i.positive_outcomes, 0) * 5 +
        CASE h.specialty_tier WHEN 'A' THEN 20 WHEN 'B' THEN 15 WHEN 'C' THEN 10 ELSE 5 END +
        CASE WHEN h.is_kol THEN 15 ELSE 0 END
    ))                                     AS engagement_score,
    CURRENT_TIMESTAMP                      AS gold_created_ts
FROM {{ ref('silver_hcp_standardized') }} h
LEFT JOIN interaction_signals i USING (hcp_id)
LEFT JOIN rx_signals r USING (hcp_id)
