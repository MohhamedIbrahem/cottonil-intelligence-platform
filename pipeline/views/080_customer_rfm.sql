-- View: customer_rfm
-- Grain: one row per customer with >= 1 order
-- Key columns: recency_days, orders_lifetime, monetary_value, R/F/M quintiles, rfm_tier
-- Derivation: as of dataset end (audit A5 'last month' policy); quintiles via NTILE(5);
--             tier label matrix uses deck p19 segment names.
-- Tiers: Champions / Loyal / Potential Loyalist / Need Attention / At Risk / Churned
CREATE OR REPLACE VIEW views.customer_rfm AS
WITH orders_agg AS (
    SELECT
        customer_id,
        COUNT(DISTINCT sales_order_id)              AS orders_lifetime,
        SUM(net_before_tax_EGP)                     AS monetary_value,
        MIN(CAST(order_date AS DATE))               AS first_order_date,
        MAX(CAST(order_date AS DATE))               AS last_order_date
    FROM raw.sales_orders
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
),
aged AS (
    SELECT
        customer_id,
        orders_lifetime,
        monetary_value,
        first_order_date,
        last_order_date,
        date_diff('day', last_order_date, DATE '{DATA_END_DATE}') AS recency_days
    FROM orders_agg
),
quintiles AS (
    SELECT
        customer_id,
        orders_lifetime,
        monetary_value,
        first_order_date,
        last_order_date,
        recency_days,
        6 - NTILE(5) OVER (ORDER BY recency_days)      AS r_score,
        NTILE(5) OVER (ORDER BY orders_lifetime DESC)  AS f_score,
        NTILE(5) OVER (ORDER BY monetary_value DESC)   AS m_score
    FROM aged
)
SELECT
    customer_id,
    orders_lifetime,
    monetary_value,
    first_order_date,
    last_order_date,
    recency_days,
    r_score,
    f_score,
    m_score,
    CASE
        WHEN r_score >= 4 AND f_score >= 4 THEN 'Champions'
        WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal'
        WHEN r_score >= 4 AND f_score <= 2 THEN 'Potential Loyalist'
        WHEN r_score =  3 AND f_score <= 2 THEN 'Need Attention'
        WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk'
        ELSE 'Churned'
    END AS rfm_tier
FROM quintiles;
