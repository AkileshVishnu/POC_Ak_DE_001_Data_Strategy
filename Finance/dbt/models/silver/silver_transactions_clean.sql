-- Silver Transactions: Validated, typed, and quality-flagged
-- Enforces: amount > 0, date <= today, typed columns

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
    CASE WHEN amount > 0 THEN 1 ELSE 0 END                         AS dq_amount_positive,
    CASE WHEN transaction_date <= CURRENT_DATE THEN 1 ELSE 0 END   AS dq_date_valid,
    _batch_id,
    _load_ts
FROM {{ source('bronze', 'bronze_transactions') }}
WHERE transaction_id IS NOT NULL
  AND amount > 0
  AND CAST(transaction_date AS DATE) <= CURRENT_DATE
