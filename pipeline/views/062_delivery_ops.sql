-- View: delivery_ops
-- Grain: one row per shipment
-- Key columns: ship/delivery dates, carrier, status, delivery days, shipping fee,
--              destination governorate, fulfilling branch, sales channel
-- Notes: every shipment in the dataset belongs to an E-commerce order (1:1).
--        ship_to_governorate is the CUSTOMER address, not the branch governorate.
CREATE OR REPLACE VIEW views.delivery_ops AS
SELECT
    d.shipment_id,
    d.sales_order_id,
    CAST(o.order_date AS DATE)                          AS order_date,
    CAST(d.ship_date AS DATE)                           AS ship_date,
    CAST(d.delivery_date AS DATE)                       AS delivery_date,
    strftime(CAST(d.ship_date AS DATE), '%Y-%m')        AS ym,
    d.carrier,
    d.fulfillment_status,
    CASE WHEN d.fulfillment_status = 'Delayed' THEN 1 ELSE 0 END AS is_delayed,
    d.ship_to_governorate                               AS destination_governorate,
    d.shipping_fee_EGP                                  AS shipping_fee_EGP,
    date_diff('day', CAST(d.ship_date AS DATE), CAST(d.delivery_date AS DATE)) AS delivery_days,
    o.sales_channel,
    o.branch_id                                         AS fulfilling_branch_id,
    b.branch_name_ar                                    AS fulfilling_branch,
    b.governorate_ar                                    AS fulfilling_branch_governorate
FROM raw.delivery_shipments d
LEFT JOIN raw.sales_orders o ON o.sales_order_id = d.sales_order_id
LEFT JOIN raw.branches b ON b.branch_id = o.branch_id
