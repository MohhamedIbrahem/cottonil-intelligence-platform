-- View: sku_monthly
-- Grain: SKU x month
-- Key columns: size/color, units, gross/discount/net, gross profit, price, discount rate, margin
-- Derivation: sales_enriched aggregated to SKU-month, joined to raw.sku_variants for
--             size/color/price multiplier (lookup context only; no fact values come from raw).
-- Notes: 695 SKUs x 97 months = 66,627 selling SKU-months. SKU-month margin range is
--        wide (~7.5-56%), unlike product-level all-time margins (audit A13).
CREATE OR REPLACE VIEW views.sku_monthly AS
WITH sku_sales AS (
    SELECT
        sku_id,
        product_id,
        ANY_VALUE(product_name_ar)                             AS product_name_ar,
        ANY_VALUE(category_en)                                 AS category_en,
        ym,
        EXTRACT(year FROM order_date)::INT                     AS year,
        COUNT(DISTINCT sales_order_id)                         AS orders,
        SUM(quantity)                                          AS units,
        SUM(gross_sales)                                       AS gross_sales,
        SUM(discount)                                          AS discount,
        SUM(net_sales)                                         AS net_sales,
        SUM(gross_profit)                                      AS gross_profit,
        SUM(net_sales) / NULLIF(SUM(quantity), 0)              AS avg_unit_price,
        SUM(discount) / NULLIF(SUM(gross_sales), 0)            AS discount_rate,
        SUM(gross_profit) / NULLIF(SUM(net_sales), 0)          AS gross_margin
    FROM views.sales_enriched
    GROUP BY sku_id, product_id, ym, EXTRACT(year FROM order_date)
)
SELECT
    s.sku_id,
    s.product_id,
    s.product_name_ar,
    s.category_en,
    v.size,
    v.color_ar,
    v.price_multiplier,
    s.ym,
    s.year,
    s.orders,
    s.units,
    s.gross_sales,
    s.discount,
    s.net_sales,
    s.gross_profit,
    s.avg_unit_price,
    s.discount_rate,
    s.gross_margin
FROM sku_sales s
LEFT JOIN raw.sku_variants v ON v.sku_id = s.sku_id;
