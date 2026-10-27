-- View: wholesale_accounts
-- Grain: one row per B2B reseller customer with >= 1 order (all time)
-- Key columns: orders, units, net, profit, AOV, margin, first/last order,
--              active months, primary channel, top category, recency, net quartile
-- Derivation: real orders tagged customer_segment = 'B2B reseller' in
--             sales_enriched, joined to the customer dimension.
-- Notes: there is no distributor-account table. Accounts are aggregated B2B
--        customers (scope matrix S22). B2B resellers mostly buy through Retail
--        POS/E-commerce, so this is a SEGMENT view, not the Wholesale channel.
CREATE OR REPLACE VIEW views.wholesale_accounts AS
WITH b2b AS (
    SELECT
        customer_id,
        COUNT(DISTINCT sales_order_id)                  AS orders,
        COUNT(*)                                        AS lines,
        SUM(quantity)                                   AS units,
        SUM(net_sales)                                  AS net_sales,
        SUM(gross_profit)                               AS gross_profit,
        MIN(CAST(order_date AS DATE))                   AS first_order_date,
        MAX(CAST(order_date AS DATE))                   AS last_order_date,
        COUNT(DISTINCT strftime(CAST(order_date AS DATE), '%Y-%m')) AS active_months,
        COUNT(DISTINCT category_en)                     AS categories
    FROM views.sales_enriched
    WHERE customer_segment = 'B2B reseller'
    GROUP BY customer_id
),
chan AS (
    SELECT customer_id, sales_channel, SUM(net_sales) AS net
    FROM views.sales_enriched
    WHERE customer_segment = 'B2B reseller'
    GROUP BY customer_id, sales_channel
),
chan_rank AS (
    SELECT
        customer_id,
        sales_channel                                   AS primary_channel,
        net                                             AS primary_channel_net,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY net DESC, sales_channel) AS rn
    FROM chan
),
cat AS (
    SELECT customer_id, category_en, SUM(net_sales) AS net
    FROM views.sales_enriched
    WHERE customer_segment = 'B2B reseller'
    GROUP BY customer_id, category_en
),
cat_rank AS (
    SELECT
        customer_id,
        category_en                                     AS top_category,
        net                                             AS top_category_net,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY net DESC, category_en) AS rn
    FROM cat
)
SELECT
    b.customer_id,
    c.customer_name_ar,
    c.governorate_ar,
    CAST(c.joined_date AS DATE)                         AS joined_date,
    c.age_band,
    b.orders,
    b.lines,
    b.units,
    b.net_sales,
    b.gross_profit,
    b.net_sales / NULLIF(b.orders, 0)                   AS avg_order_value,
    b.gross_profit / NULLIF(b.net_sales, 0)             AS gross_margin,
    b.first_order_date,
    b.last_order_date,
    b.active_months,
    b.categories,
    cr.primary_channel,
    catr.top_category,
    date_diff('day', b.last_order_date, DATE '{DATA_END_DATE}') AS days_since_last_order,
    CASE
        WHEN date_diff('day', b.last_order_date, DATE '{DATA_END_DATE}') <= 90 THEN 'Active (<=90d)'
        WHEN date_diff('day', b.last_order_date, DATE '{DATA_END_DATE}') <= 365 THEN 'Lapsed (91-365d)'
        ELSE 'Dormant (>365d)'
    END                                                 AS recency_bucket,
    CASE
        WHEN b.orders = 1 THEN '1 order'
        WHEN b.orders <= 3 THEN '2-3 orders'
        WHEN b.orders <= 6 THEN '4-6 orders'
        ELSE '7+ orders'
    END                                                 AS repeat_bucket,
    NTILE(4) OVER (ORDER BY b.net_sales DESC)           AS net_quartile
FROM b2b b
LEFT JOIN raw.customers c ON c.customer_id = b.customer_id
LEFT JOIN chan_rank cr ON cr.customer_id = b.customer_id AND cr.rn = 1
LEFT JOIN cat_rank catr ON catr.customer_id = b.customer_id AND catr.rn = 1
