-- View: channel_monthly
-- Grain: month x sales channel
-- Key columns: orders, customers, units, gross/discount/net, gross profit, AOV, margin
-- Derivation: sales_enriched aggregated to channel-month (Retail POS / Wholesale / E-commerce).
-- Notes: 97 months x 3 channels = 291 rows. Guest orders count in revenue and orders but
--        never in customers (audit A4). This is the only omnichannel history available:
--        no sessions, funnels, carts, app users, or marketplace data.
CREATE OR REPLACE VIEW views.channel_monthly AS
SELECT
    ym,
    EXTRACT(year FROM order_date)::INT                         AS year,
    sales_channel,
    COUNT(DISTINCT sales_order_id)                             AS orders,
    COUNT(DISTINCT customer_id) FILTER (WHERE customer_id IS NOT NULL) AS customers,
    SUM(quantity)                                              AS units,
    SUM(gross_sales)                                           AS gross_sales,
    SUM(discount)                                              AS discount,
    SUM(net_sales)                                             AS net_sales,
    SUM(gross_profit)                                          AS gross_profit,
    SUM(net_sales) / NULLIF(COUNT(DISTINCT sales_order_id), 0) AS avg_order_value,
    SUM(discount) / NULLIF(SUM(gross_sales), 0)                AS discount_rate,
    SUM(gross_profit) / NULLIF(SUM(net_sales), 0)              AS gross_margin
FROM views.sales_enriched
GROUP BY ym, EXTRACT(year FROM order_date), sales_channel;
