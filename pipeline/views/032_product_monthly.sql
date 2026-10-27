-- View: product_monthly
-- Grain: product x month
-- Key columns: units, gross/discount/net, gross profit, average price, discount rate, margin
-- Derivation: sales_enriched aggregated to product-month; product names/category/audience
--             carried from the catalog.
-- Notes: 139 products x 97 months = 13,483 selling product-months. Product-level all-time
--        margins are tightly clustered (~37.5-39.4%); SKU-month margins vary much more,
--        so low-margin alerts belong on views.sku_monthly (audit A13).
CREATE OR REPLACE VIEW views.product_monthly AS
SELECT
    product_id,
    ANY_VALUE(product_name_ar)                                 AS product_name_ar,
    ANY_VALUE(category_en)                                     AS category_en,
    ANY_VALUE(audience)                                        AS audience,
    ym,
    EXTRACT(year FROM order_date)::INT                         AS year,
    COUNT(DISTINCT sales_order_id)                             AS orders,
    SUM(quantity)                                              AS units,
    SUM(gross_sales)                                           AS gross_sales,
    SUM(discount)                                              AS discount,
    SUM(net_sales)                                             AS net_sales,
    SUM(gross_profit)                                          AS gross_profit,
    SUM(net_sales) / NULLIF(SUM(quantity), 0)                  AS avg_unit_price,
    SUM(discount) / NULLIF(SUM(gross_sales), 0)                AS discount_rate,
    SUM(gross_profit) / NULLIF(SUM(net_sales), 0)              AS gross_margin
FROM views.sales_enriched
GROUP BY product_id, ym, EXTRACT(year FROM order_date);
