-- View: top_products
-- Grain: product x month
-- Key columns: units, net, profit, orders
-- Notes: 'Top products last month' style questions (Sales page / assistant).
CREATE OR REPLACE VIEW views.top_products AS
SELECT
    ym,
    product_id,
    ANY_VALUE(product_name_ar)          AS product_name_ar,
    ANY_VALUE(category_en)              AS category_en,
    ANY_VALUE(audience)                 AS audience,
    SUM(quantity)                       AS units,
    SUM(net_sales)                      AS net_sales,
    SUM(gross_profit)                   AS gross_profit,
    COUNT(DISTINCT sales_order_id)      AS orders
FROM views.sales_enriched
GROUP BY ym, product_id;
