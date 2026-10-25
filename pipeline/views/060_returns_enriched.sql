-- View: returns_enriched
-- Grain: one row per return
-- Key columns: reason, refund amount (raw + capped), returned line net, product/branch context
-- Notes: refund_capped = LEAST(refund, line net) per audit policy A3.
CREATE OR REPLACE VIEW views.returns_enriched AS
SELECT
    r.return_id,
    r.sales_order_id,
    r.sales_line_id,
    CAST(r.return_date AS DATE)                        AS return_date,
    strftime(CAST(r.return_date AS DATE), '%Y-%m')     AS ym,
    r.sku_id,
    e.product_id,
    e.category_en,
    e.audience,
    e.branch_id,
    e.branch_governorate_ar,
    e.sales_channel,
    e.customer_id,
    COALESCE(e.customer_segment, 'Guest')              AS customer_segment,
    r.return_quantity,
    r.refund_amount_EGP                                AS refund_amount,
    e.net_sales                                        AS refunded_line_net,
    LEAST(r.refund_amount_EGP, e.net_sales)            AS refund_capped,
    r.reason,
    r.refund_method
FROM raw.sales_returns r
LEFT JOIN views.sales_enriched e ON e.sales_line_id = r.sales_line_id;
