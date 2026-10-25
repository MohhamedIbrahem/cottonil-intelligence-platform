-- View: product_overview
-- Grain: one row per product (all-time profile)
-- Key columns: variants, units, net, profit, first/last order
-- Notes: Master product profile (assortment / profitability).
CREATE OR REPLACE VIEW views.product_overview AS
WITH variant_counts AS (
    SELECT product_id, COUNT(*) AS variants
    FROM raw.sku_variants
    GROUP BY product_id
),
product_sales AS (
    SELECT
        product_id,
        SUM(quantity)                              AS units,
        SUM(net_line_EGP)                          AS net_sales,
        SUM(margin_EGP)                            AS gross_profit,
        MIN(CAST(order_date AS DATE))              AS first_order_date,
        MAX(CAST(order_date AS DATE))              AS last_order_date
    FROM raw.sales_order_items
    GROUP BY product_id
)
SELECT
    p.product_id,
    p.product_name_ar,
    p.category_en,
    p.audience,
    p.listed_price_EGP,
    COALESCE(v.variants, 0)                      AS variants,
    COALESCE(s.units, 0)                         AS units,
    COALESCE(s.net_sales, 0)                     AS net_sales,
    COALESCE(s.gross_profit, 0)                  AS gross_profit,
    s.first_order_date,
    s.last_order_date
FROM raw.products_catalog p
LEFT JOIN variant_counts v USING (product_id)
LEFT JOIN product_sales s USING (product_id);
