-- View: procurement_monthly
-- Grain: po month x supplier
-- Key columns: POs, lines, units, value, lead days, on-time rate, partial receipts
-- Derivation: PO header + items, grouped to supplier-month. on_time = item
--             delivery_date <= po_date + supplier payment_terms_days.
-- Notes: value_EGP is ABSOLUTE-ONLY (audit A1) - never compare to COGS or revenue.
--        The on-time threshold uses payment terms because the dataset has no
--        contractual promised-delivery date.
CREATE OR REPLACE VIEW views.procurement_monthly AS
WITH lines AS (
    SELECT
        strftime(CAST(p.po_date AS DATE), '%Y-%m')      AS ym,
        p.supplier_id,
        p.po_id,
        p.po_status,
        p.payment_terms_days,
        i.po_line_id,
        i.quantity,
        i.line_cost_EGP,
        date_diff('day', CAST(p.po_date AS DATE), CAST(i.delivery_date AS DATE)) AS lead_days,
        CASE
            WHEN CAST(i.delivery_date AS DATE)
                 <= CAST(p.po_date AS DATE) + CAST(p.payment_terms_days AS INTEGER) THEN 1
            ELSE 0
        END                                             AS on_time
    FROM raw.purchase_orders p
    JOIN raw.purchase_order_items i ON i.po_id = p.po_id
)
SELECT
    l.ym,
    l.supplier_id,
    s.supplier_name_ar,
    s.material_type,
    s.city_country,
    ANY_VALUE(l.payment_terms_days)                     AS payment_terms_days,
    COUNT(DISTINCT l.po_id)                             AS n_purchase_orders,
    COUNT(*)                                            AS n_lines,
    SUM(l.quantity)                                     AS units,
    SUM(l.line_cost_EGP)                                AS value_EGP,
    AVG(l.lead_days)                                    AS avg_lead_days,
    AVG(l.on_time)                                      AS on_time_rate,
    COUNT(DISTINCT CASE WHEN l.po_status = 'Partial receipt' THEN l.po_id END) AS partial_pos
FROM lines l
JOIN raw.suppliers s ON s.supplier_id = l.supplier_id
GROUP BY l.ym, l.supplier_id, s.supplier_name_ar, s.material_type, s.city_country
