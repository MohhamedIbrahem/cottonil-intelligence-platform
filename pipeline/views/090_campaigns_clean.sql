-- View: campaigns_clean
-- Grain: one row per campaign
-- Key columns: spend, impressions, clicks, ctr, budget utilization, attributed_orders_real, attributed_net_real
-- Derivation: attribution REBUILT from real sales orders whose date falls in the
--             campaign window and whose customer governorate matches the campaign
--             governorate (guest orders excluded because they carry no governorate).
-- Notes: NEVER use marketing_campaigns.orders_attributed for revenue math (audit A2:
--        it sums to ~24.1M orders vs 540K real orders).
CREATE OR REPLACE VIEW views.campaigns_clean AS
WITH daily_gov AS (
    SELECT
        c.governorate_ar                            AS governorate_ar,
        CAST(o.order_date AS DATE)                  AS order_date,
        COUNT(DISTINCT o.sales_order_id)            AS orders,
        SUM(o.net_before_tax_EGP)                   AS net_sales
    FROM raw.sales_orders o
    JOIN raw.customers c ON c.customer_id = o.customer_id
    WHERE o.customer_id IS NOT NULL
    GROUP BY 1, 2
),
attributed AS (
    SELECT
        m.campaign_id,
        SUM(g.orders)      AS attributed_orders_real,
        SUM(g.net_sales)   AS attributed_net_real
    FROM raw.marketing_campaigns m
    JOIN daily_gov g
      ON g.governorate_ar = m.governorate_ar
     AND g.order_date >= CAST(m.start_date AS DATE)
     AND g.order_date <= CAST(m.end_date AS DATE)
    GROUP BY m.campaign_id
)
SELECT
    m.campaign_id,
    CAST(m.start_date AS DATE)      AS start_date,
    CAST(m.end_date   AS DATE)      AS end_date,
    m.channel,
    m.target_audience,
    m.governorate_ar,
    m.budget_EGP,
    m.spend_EGP,
    m.impressions,
    m.clicks,
    m.clicks / NULLIF(m.impressions, 0)          AS ctr,
    m.spend_EGP / NULLIF(m.budget_EGP, 0)        AS budget_utilization,
    m.orders_attributed                          AS orders_attributed_reported,
    COALESCE(a.attributed_orders_real, 0)        AS attributed_orders_real,
    COALESCE(a.attributed_net_real, 0)           AS attributed_net_real
FROM raw.marketing_campaigns m
LEFT JOIN attributed a ON a.campaign_id = m.campaign_id;
