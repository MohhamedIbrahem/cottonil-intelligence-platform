-- View: branch_daily
-- Grain: branch x day
-- Key columns: orders, customers, units, net, profit, discount
-- Notes: Period-filterable branch metrics (dashboards sum over selected period).
CREATE OR REPLACE VIEW views.branch_daily AS
SELECT
    branch_id,
    branch_governorate_ar               AS governorate_ar,
    order_date,
    ym,
    COUNT(DISTINCT sales_order_id)      AS orders,
    COUNT(DISTINCT customer_id) FILTER (WHERE customer_id IS NOT NULL) AS active_customers,
    SUM(quantity)                       AS units,
    SUM(net_sales)                      AS net_sales,
    SUM(gross_sales)                    AS gross_sales,
    SUM(discount)                       AS discount,
    SUM(gross_profit)                   AS gross_profit
FROM views.sales_enriched
GROUP BY branch_id, branch_governorate_ar, order_date, ym;
