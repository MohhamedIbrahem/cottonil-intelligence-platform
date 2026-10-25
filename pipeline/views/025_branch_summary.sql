-- View: branch_summary
-- Grain: one row per branch (all-time profile)
-- Key columns: net, orders, avg basket, profit, margin %, first/last order, customers
-- Notes: All-time profile; period-filtered dashboards should use branch_daily.
CREATE OR REPLACE VIEW views.branch_summary AS
SELECT
    branch_id,
    ANY_VALUE(branch_name_ar)                                    AS branch_name_ar,
    ANY_VALUE(branch_governorate_ar)                             AS governorate_ar,
    ANY_VALUE(branch_type)                                       AS branch_type,
    SUM(net_sales)                                               AS net_sales,
    COUNT(DISTINCT sales_order_id)                               AS orders,
    SUM(net_sales) / NULLIF(COUNT(DISTINCT sales_order_id), 0)   AS avg_basket,
    SUM(quantity)                                                AS units,
    SUM(gross_profit)                                            AS gross_profit,
    SUM(gross_profit) / NULLIF(SUM(net_sales), 0)                AS margin_pct,
    COUNT(DISTINCT customer_id) FILTER (WHERE customer_id IS NOT NULL) AS customers,
    MIN(order_date)                                              AS first_order_date,
    MAX(order_date)                                              AS last_order_date
FROM views.sales_enriched
GROUP BY branch_id;
