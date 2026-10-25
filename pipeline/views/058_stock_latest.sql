-- View: stock_latest
-- Grain: latest month snapshot of stock_status
-- Key columns: same as stock_status
-- Notes: dashboard KPI view ('latest month' = max year_month in the dataset).
CREATE OR REPLACE VIEW views.stock_latest AS
SELECT *
FROM views.stock_status
WHERE year_month = (SELECT MAX(year_month) FROM views.stock_status);
