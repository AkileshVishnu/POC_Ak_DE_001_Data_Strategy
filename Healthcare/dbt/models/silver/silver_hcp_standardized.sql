-- Silver HCP Standardized: Cleansed and validated HCP records
-- Normalizes name formats, validates NPI, adds data quality flags

SELECT
    hcp_id,
    TRIM(npi)                                               AS npi,
    UPPER(TRIM(first_name))                                 AS first_name,
    UPPER(TRIM(last_name))                                  AS last_name,
    TRIM(full_name)                                         AS full_name,
    UPPER(TRIM(specialty_code))                             AS specialty_code,
    TRIM(specialty_name)                                    AS specialty_name,
    specialty_tier,
    UPPER(TRIM(state))                                      AS state,
    territory_id,
    degree,
    CAST(years_in_practice AS INTEGER)                      AS years_in_practice,
    CAST(is_key_opinion_leader AS BOOLEAN)                  AS is_kol,
    CAST(is_investigator AS BOOLEAN)                        AS is_investigator,
    CAST(created_date AS DATE)                              AS created_date,
    CAST(updated_date AS DATE)                              AS updated_date,
    CASE
        WHEN npi IS NULL OR LENGTH(TRIM(npi)) != 10 THEN 0
        ELSE 1
    END                                                     AS dq_npi_valid,
    CASE
        WHEN first_name IS NULL OR first_name = '' THEN 0
        ELSE 1
    END                                                     AS dq_name_complete,
    CASE WHEN specialty_code IS NULL THEN 0 ELSE 1 END      AS dq_specialty_present,
    _batch_id,
    _load_ts
FROM {{ source('bronze', 'bronze_hcp_master') }}
WHERE hcp_id IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY hcp_id ORDER BY _load_ts DESC) = 1
