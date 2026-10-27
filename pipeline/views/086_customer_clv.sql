-- View: customer_clv
-- Grain: one row per cataloged customer (85,000), including customers with zero orders
-- Key columns: lifetime orders/units/net/profit (historical CLV), AOV, margin, recency,
--              tenure, purchase flag, churn status
-- Derivation: raw.customers LEFT JOIN sales_enriched lifetime aggregates. CLV is historical
--             gross profit, not a predictive model. Churn = no purchase for >=365 days for a
--             customer with >=365 days tenure (audit A12). Non-buyers are 'Never purchased'.
-- Notes: ~17% of the catalog has never purchased; guests (~19% of orders) are absent from
--        customer metrics (audit A4). The page's logistic holdout tests whether churn is
--        predictable at all - held-out AUC is reported next to this factual profile.
CREATE OR REPLACE VIEW views.customer_clv AS
WITH sales AS (
    SELECT
        customer_id,
        COUNT(DISTINCT sales_order_id)                      AS orders_lifetime,
        COUNT(*)                                            AS lines_lifetime,
        SUM(quantity)                                       AS units_lifetime,
        SUM(net_sales)                                      AS net_sales_lifetime,
        SUM(gross_profit)                                   AS gross_profit_lifetime,
        MIN(CAST(order_date AS DATE))                       AS first_order_date,
        MAX(CAST(order_date AS DATE))                       AS last_order_date,
        COUNT(DISTINCT ym)                                  AS active_months
    FROM views.sales_enriched
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
),
profile AS (
    SELECT
        c.customer_id,
        c.customer_name_ar,
        c.customer_segment,
        c.governorate_ar,
        c.age_band,
        CAST(c.joined_date AS DATE)                         AS joined_date,
        GREATEST(date_diff('day', CAST(c.joined_date AS DATE), DATE '{DATA_END_DATE}'), 0)
                                                            AS tenure_days,
        s.orders_lifetime,
        s.lines_lifetime,
        s.units_lifetime,
        s.net_sales_lifetime,
        s.gross_profit_lifetime,
        s.first_order_date,
        s.last_order_date,
        s.active_months,
        CASE
            WHEN s.last_order_date IS NULL THEN NULL
            ELSE date_diff('day', s.last_order_date, DATE '{DATA_END_DATE}')
        END                                                 AS recency_days
    FROM raw.customers c
    LEFT JOIN sales s ON s.customer_id = c.customer_id
)
SELECT
    customer_id,
    customer_name_ar,
    customer_segment,
    governorate_ar,
    age_band,
    joined_date,
    tenure_days,
    first_order_date,
    last_order_date,
    recency_days,
    orders_lifetime,
    lines_lifetime,
    units_lifetime,
    net_sales_lifetime,
    gross_profit_lifetime,
    net_sales_lifetime / NULLIF(orders_lifetime, 0)         AS avg_order_value,
    gross_profit_lifetime / NULLIF(net_sales_lifetime, 0)   AS gross_margin,
    active_months,
    orders_lifetime IS NOT NULL                             AS has_purchased,
    CASE
        WHEN orders_lifetime IS NULL THEN 'Never purchased'
        WHEN tenure_days < 365 THEN 'Insufficient history'
        WHEN recency_days >= 365 THEN 'Churned'
        ELSE 'Active'
    END                                                     AS churn_status,
    orders_lifetime IS NOT NULL AND tenure_days >= 365      AS is_churn_eligible
FROM profile;
