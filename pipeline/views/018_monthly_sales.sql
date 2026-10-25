-- View: monthly_sales
-- Grain: one row per month
-- Key columns: ym, net, gross_profit, orders, units, active customers, per-channel splits
-- Notes: Powers executive trend + channel mix.
CREATE OR REPLACE VIEW views.monthly_sales AS
SELECT
    ym,
    EXTRACT(year FROM order_date)::INT                                        AS year,
    SUM(net_sales)                                                            AS net_sales,
    SUM(gross_profit)                                                         AS gross_profit,
    COUNT(DISTINCT sales_order_id)                                            AS orders,
    SUM(quantity)                                                             AS units,
    COUNT(DISTINCT customer_id) FILTER (WHERE customer_id IS NOT NULL)        AS active_customers,
    SUM(net_sales) FILTER (WHERE sales_channel = 'Retail POS')                AS retail_pos_net,
    SUM(net_sales) FILTER (WHERE sales_channel = 'Wholesale / reseller')     AS wholesale_net,
    SUM(net_sales) FILTER (WHERE sales_channel = 'E-commerce')                AS ecommerce_net
FROM views.sales_enriched
GROUP BY ym, EXTRACT(year FROM order_date)::INT;
