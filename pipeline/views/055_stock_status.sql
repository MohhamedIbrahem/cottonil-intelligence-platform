-- View: stock_status
-- Grain: month x location x category + status bucket
-- Key columns: stock_status in ('Low stock' / 'Overstock' / 'In stock')
-- Derivation: stockout_risk >= 0.60 -> 'Low stock'; else top decile of closing_units
--             within (month, category) -> 'Overstock'; else 'In stock'
-- Notes: bucket policy documented here (deck p5-style three-state).
CREATE OR REPLACE VIEW views.stock_status AS
WITH bucketed AS (
    SELECT
        s.year_month,
        s.stock_location_id,
        s.stock_location_type,
        COALESCE(b.branch_name_ar, w.warehouse_label) AS location_label,
        COALESCE(b.governorate_ar, w.governorate_ar)  AS location_governorate_ar,
        s.product_category,
        s.closing_units,
        s.closing_stock_value_EGP                     AS closing_stock_value,
        s.stockout_risk_score,
        PERCENT_RANK() OVER (
            PARTITION BY s.year_month, s.product_category
            ORDER BY s.closing_units
        ) AS pct_units
    FROM raw.monthly_stock s
    LEFT JOIN raw.branches b ON b.branch_id = s.stock_location_id
    LEFT JOIN raw.warehouses w ON w.warehouse_id = s.stock_location_id
)
SELECT
    year_month,
    stock_location_id,
    stock_location_type,
    location_label,
    location_governorate_ar,
    product_category,
    closing_units,
    closing_stock_value,
    stockout_risk_score,
    CASE
        WHEN stockout_risk_score >= 0.60 THEN 'Low stock'
        WHEN pct_units >= 0.90 THEN 'Overstock'
        ELSE 'In stock'
    END AS stock_status
FROM bucketed;
