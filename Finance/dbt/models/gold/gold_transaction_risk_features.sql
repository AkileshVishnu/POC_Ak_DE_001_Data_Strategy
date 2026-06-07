-- Gold Transaction Risk Features
-- Point-in-time correct feature engineering for fraud detection
-- All aggregations use ONLY data available before each transaction's timestamp

WITH historical_customer AS (
    SELECT
        t.transaction_id,
        t.customer_id,
        t.transaction_date,
        -- 30-day rolling window: only data BEFORE this transaction
        COUNT(h.transaction_id)                             AS customer_tx_count_30d,
        COALESCE(AVG(h.amount), 0)                          AS customer_avg_amount_30d,
        COALESCE(MAX(h.amount), 0)                          AS customer_max_amount_30d,
        COALESCE(SUM(h.amount), 0)                          AS customer_total_amount_30d,
        COUNT(CASE WHEN h.transaction_date >= t.transaction_date - INTERVAL '7 days'
                   THEN 1 END)                              AS customer_tx_count_7d,
        COALESCE(DATEDIFF('day',
            MAX(CASE WHEN h.transaction_id != t.transaction_id THEN h.transaction_date END),
            t.transaction_date), 999)                       AS days_since_last_tx,
        COUNT(DISTINCT h.transaction_state)                 AS distinct_states_30d,
        COALESCE(SUM(CAST(h.is_fraud AS INTEGER)), 0)       AS prior_fraud_count
    FROM {{ ref('silver_transactions_clean') }} t
    LEFT JOIN {{ ref('silver_transactions_clean') }} h
        ON h.customer_id = t.customer_id
        AND h.transaction_date BETWEEN t.transaction_date - INTERVAL '30 days'
                                   AND t.transaction_date       -- PIT: upper bound = event time
        AND h.transaction_id != t.transaction_id                -- exclude current transaction
    GROUP BY t.transaction_id, t.customer_id, t.transaction_date
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
    h.customer_tx_count_30d,
    h.customer_avg_amount_30d,
    h.customer_max_amount_30d,
    h.customer_total_amount_30d,
    h.customer_tx_count_7d,
    h.days_since_last_tx,
    h.distinct_states_30d,
    h.prior_fraud_count,
    CASE WHEN h.customer_avg_amount_30d > 0
         THEN t.amount / h.customer_avg_amount_30d
         ELSE 1.0 END                                       AS amount_vs_avg_ratio,
    CASE WHEN t.transaction_hour BETWEEN 0 AND 4 THEN 1 ELSE 0 END AS is_late_night,
    COALESCE(c.bureau_score, 650)                           AS bureau_score,
    COALESCE(c.credit_utilization_pct, 0.5)                 AS credit_utilization_pct,
    COALESCE(c.num_derogatory_marks, 0)                     AS num_derogatory_marks,
    c.customer_tenure_days,
    COALESCE(m.risk_flag, FALSE)                            AS merchant_risk_flag,
    t.is_fraud,
    CURRENT_TIMESTAMP                                       AS feature_ts
FROM {{ ref('silver_transactions_clean') }} t
LEFT JOIN historical_customer h USING (transaction_id)
LEFT JOIN {{ ref('gold_customer_360') }} c USING (customer_id)
LEFT JOIN {{ ref('silver_merchants_clean') }} m USING (merchant_id)
