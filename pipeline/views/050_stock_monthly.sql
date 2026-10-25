-- View: stock_monthly
-- Grain: month x location x category
-- Key columns: closing units/value, stockout risk, location label/governorate
-- Notes: raw fields kept as-is (audit A7); location labels joined for readability.
CREATE OR REPLACE VIEW views.stock_monthly AS
SELECT
    s.year_month                                      AS year_month,
    s.stock_location_id,
    s.stock_location_type,
    COALESCE(b.branch_name_ar, w.warehouse_label)     AS location_label,
    COALESCE(b.governorate_ar, w.governorate_ar)      AS location_governorate_ar,
    s.product_category,
    s.closing_units,
    s.closing_stock_value_EGP                         AS closing_stock_value,
    s.stockout_risk_score
FROM raw.monthly_stock s
LEFT JOIN raw.branches b ON b.branch_id = s.stock_location_id
LEFT JOIN raw.warehouses w ON w.warehouse_id = s.stock_location_id;
