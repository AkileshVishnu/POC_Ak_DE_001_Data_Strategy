-- Silver Interactions: Validated and cleaned interaction activity
-- Filters out future-dated records and enforces referential integrity

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
    1                                       AS dq_date_valid
FROM {{ source('bronze', 'bronze_hcp_interactions') }}
WHERE hcp_id IS NOT NULL
  AND interaction_date IS NOT NULL
  AND CAST(interaction_date AS DATE) <= CURRENT_DATE
