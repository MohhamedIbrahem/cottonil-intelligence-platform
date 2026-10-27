-- View: transfer_ops
-- Grain: one row per inventory transfer
-- Key columns: transfer date/status, source warehouse, destination branch,
--              transport cost, lines, SKUs, units, cost per unit
-- Notes: transport_cost_EGP is a transfer-level cost. It is aggregated here once
--        per transfer, so summing it never double-counts transfer items.
CREATE OR REPLACE VIEW views.transfer_ops AS
SELECT
    t.transfer_id,
    CAST(t.transfer_date AS DATE)                       AS transfer_date,
    strftime(CAST(t.transfer_date AS DATE), '%Y-%m')    AS ym,
    t.transfer_status,
    t.source_warehouse_id,
    w.warehouse_label                                   AS source_warehouse,
    w.governorate_ar                                    AS source_governorate,
    t.destination_branch_id,
    b.branch_name_ar                                    AS destination_branch,
    b.governorate_ar                                    AS destination_governorate,
    b.retail_location_type                              AS destination_location_type,
    t.transport_cost_EGP                                AS transport_cost_EGP,
    COUNT(i.transfer_line_id)                           AS n_lines,
    COUNT(DISTINCT i.sku_id)                            AS n_skus,
    COALESCE(SUM(i.quantity_units), 0)                  AS units,
    t.transport_cost_EGP / NULLIF(SUM(i.quantity_units), 0) AS cost_per_unit
FROM raw.inventory_transfers t
LEFT JOIN raw.warehouses w ON w.warehouse_id = t.source_warehouse_id
LEFT JOIN raw.branches b ON b.branch_id = t.destination_branch_id
LEFT JOIN raw.inventory_transfer_items i ON i.transfer_id = t.transfer_id
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
