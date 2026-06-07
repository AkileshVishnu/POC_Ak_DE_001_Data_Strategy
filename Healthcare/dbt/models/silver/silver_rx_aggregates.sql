-- Silver Rx Aggregates: Validated prescription aggregate data
-- Enforces non-negative counts and valid market share

SELECT
    rx_id,
    hcp_id,
    product,
    CAST(period_month AS INTEGER)           AS period_month,
    CAST(period_year AS INTEGER)            AS period_year,
    CAST(total_rx_count AS INTEGER)         AS total_rx_count,
    CAST(new_patient_starts AS INTEGER)     AS new_patient_starts,
    CAST(market_share_pct AS DOUBLE)        AS market_share_pct,
    source_system
FROM {{ source('bronze', 'bronze_rx_aggregates') }}
WHERE hcp_id IS NOT NULL
  AND total_rx_count >= 0
  AND market_share_pct BETWEEN 0 AND 1
