-- View: sales_enriched
-- Grain: one row per sales order line (transaction spine for all revenue analytics)
-- Key columns: order_date, year, ym, channel, payment, branch/governorate, customer
--              segment (Guest-safe), category, audience, price/cost, gross/discount/net/margin
-- Joins: items -> orders (channel/payment/customer/status), branches, products, LEFT JOIN customers
-- Notes: Guest orders (~19%, audit A4) get customer_segment='Guest'.
CREATE OR REPLACE VIEW views.sales_enriched AS
SELECT
    i.sales_line_id,
    i.sales_order_id,
    CAST(i.order_date AS DATE)                                   AS order_date,
    EXTRACT(year FROM CAST(i.order_date AS DATE))::INT           AS year,
    strftime(CAST(i.order_date AS DATE), '%Y-%m')                AS ym,
    o.sales_channel                                              AS sales_channel,
    o.payment_method                                             AS payment_method,
    o.status                                                     AS order_status,
    i.branch_id,
    b.branch_name_ar                                             AS branch_name_ar,
    b.governorate_ar                                             AS branch_governorate_ar,
    b.city_ar                                                    AS branch_city_ar,
    b.retail_location_type                                       AS branch_type,
    o.customer_id                                                AS customer_id,
    COALESCE(c.customer_segment, 'Guest')                        AS customer_segment,
    c.age_band                                                   AS customer_age_band,
    c.governorate_ar                                             AS customer_governorate_ar,
    i.sku_id,
    i.product_id,
    p.product_name_ar                                            AS product_name_ar,
    p.category_en                                                AS category_en,
    p.audience                                                   AS audience,
    i.quantity,
    i.unit_price_EGP                                             AS unit_price,
    i.unit_cost_EGP                                              AS unit_cost,
    i.gross_line_EGP                                             AS gross_sales,
    i.discount_line_EGP                                          AS discount,
    i.net_line_EGP                                               AS net_sales,
    i.margin_EGP                                                 AS gross_profit
FROM raw.sales_order_items i
JOIN raw.sales_orders o ON o.sales_order_id = i.sales_order_id
JOIN raw.branches b ON b.branch_id = i.branch_id
JOIN raw.products_catalog p ON p.product_id = i.product_id
LEFT JOIN raw.customers c ON c.customer_id = o.customer_id;
