-- View: supplier_pos
-- Grain: one row per supplier (all-time procurement profile)
-- Key columns: #POs, lines, units, value, avg lead days, on-time %, first/last PO
-- Derivation: on-time = delivery_date <= po_date + supplier payment_terms_days
-- Notes: total_value_EGP is NOT comparable to COGS/revenue (audit A1 scale anomaly).
CREATE OR REPLACE VIEW views.supplier_pos AS
SELECT
    s.supplier_id,
    s.supplier_name_ar,
    s.material_type,
    s.city_country,
    s.payment_terms_days,
    COUNT(DISTINCT p.po_id)                            AS n_purchase_orders,
    COUNT(*)                                           AS n_lines,
    SUM(i.quantity)                                    AS total_units,
    SUM(i.line_cost_EGP)                               AS total_value_EGP,
    AVG(date_diff('day', CAST(p.po_date AS DATE), CAST(i.delivery_date AS DATE))) AS avg_lead_days,
    AVG(
        CASE
            WHEN CAST(i.delivery_date AS DATE)
                 <= CAST(p.po_date AS DATE) + CAST(p.payment_terms_days AS INTEGER) THEN 1.0
            ELSE 0.0
        END
    )                                                  AS on_time_pct,
    MIN(CAST(p.po_date AS DATE))                       AS first_po_date,
    MAX(CAST(p.po_date AS DATE))                       AS last_po_date
FROM raw.suppliers s
JOIN raw.purchase_orders p ON p.supplier_id = s.supplier_id
JOIN raw.purchase_order_items i ON i.po_id = p.po_id
GROUP BY ALL;
