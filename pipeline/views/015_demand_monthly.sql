-- View: demand_monthly
-- Grain: month x product category (complete + partial months)
-- Key columns: units, net sales, gross profit, orders, customers, average net price, margin
-- Derivation: complete calendar months only for model fitting; 2026-10 is partial
--             (dataset ends 2026-10-18) and is flagged so pages/backtests can exclude it.
-- Notes: demand history is 96 complete months (2018-11 through 2026-09) plus the
--        partial October 2026 month. Category-month grain = 1,552 rows.
CREATE OR REPLACE VIEW views.demand_monthly AS
SELECT
    ym,
    EXTRACT(year FROM order_date)::INT                         AS year,
    category_en,
    SUM(quantity)                                              AS units,
    SUM(net_sales)                                             AS net_sales,
    SUM(gross_profit)                                          AS gross_profit,
    COUNT(DISTINCT sales_order_id)                             AS orders,
    COUNT(DISTINCT customer_id) FILTER (WHERE customer_id IS NOT NULL) AS customers,
    SUM(net_sales) / NULLIF(SUM(quantity), 0)                  AS avg_unit_price,
    SUM(gross_profit) / NULLIF(SUM(net_sales), 0)              AS gross_margin,
    (date_trunc('month', MIN(order_date)) + INTERVAL 1 MONTH - INTERVAL 1 DAY)
        <= DATE '{DATA_END_DATE}'                              AS is_complete_month
FROM views.sales_enriched
GROUP BY ym, EXTRACT(year FROM order_date), category_en;
