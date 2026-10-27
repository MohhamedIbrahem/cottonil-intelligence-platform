-- View: replenishment_signals
-- Grain: latest stock month x location x category (1,472 cells)
-- Key columns: closing units/value, risk, 90-day velocity, cover days, reorder units/value, signal
-- Derivation: views.stock_latest LEFT JOIN branch sales velocity (90 days to DATA_END_DATE)
--             or warehouse outgoing-transfer velocity (90 days). Rule: target 45 days of cover;
--             reorder = ceil(velocity * 45 - closing_units) when cover < 45 days.
-- Notes: rules-based heuristic, not an optimiser. Branches use POS sales velocity; warehouses
--        use outgoing transfers because warehouses do not sell. Category level only - the stock
--        snapshot has no SKU detail (scope S18). Lead times and supplier constraints are absent.
CREATE OR REPLACE VIEW views.replenishment_signals AS
WITH branch_velocity AS (
    SELECT
        branch_id,
        category_en,
        SUM(quantity) / 90.0                                AS velocity_90d
    FROM views.sales_enriched
    WHERE order_date BETWEEN DATE '{DATA_END_DATE}' - INTERVAL 89 DAY
                         AND DATE '{DATA_END_DATE}'
    GROUP BY branch_id, category_en
),
warehouse_velocity AS (
    SELECT
        t.source_warehouse_id,
        p.category_en,
        SUM(i.quantity_units) / 90.0                        AS velocity_90d
    FROM raw.inventory_transfers t
    JOIN raw.inventory_transfer_items i ON i.transfer_id = t.transfer_id
    JOIN raw.sku_variants v ON v.sku_id = i.sku_id
    JOIN raw.products_catalog p ON p.product_id = v.product_id
    WHERE t.transfer_date BETWEEN DATE '{DATA_END_DATE}' - INTERVAL 89 DAY
                              AND DATE '{DATA_END_DATE}'
    GROUP BY t.source_warehouse_id, p.category_en
),
velocity AS (
    SELECT
        s.year_month,
        s.stock_location_id,
        s.stock_location_type,
        s.location_label,
        s.location_governorate_ar,
        s.product_category,
        s.closing_units,
        s.closing_stock_value,
        s.stockout_risk_score,
        s.stock_status,
        CASE
            WHEN s.stock_location_type = 'Branch' THEN b.velocity_90d
            ELSE w.velocity_90d
        END                                                 AS velocity_90d,
        CASE
            WHEN s.stock_location_type = 'Branch' THEN 'Branch sales'
            ELSE 'Warehouse transfers'
        END                                                 AS velocity_source
    FROM views.stock_latest s
    LEFT JOIN branch_velocity b
           ON b.branch_id = s.stock_location_id
          AND b.category_en = s.product_category
    LEFT JOIN warehouse_velocity w
           ON w.source_warehouse_id = s.stock_location_id
          AND w.category_en = s.product_category
),
covered AS (
    SELECT
        *,
        closing_units / NULLIF(velocity_90d, 0)             AS cover_days,
        closing_stock_value / NULLIF(closing_units, 0)      AS stock_value_per_unit
    FROM velocity
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
    stock_status,
    velocity_90d,
    velocity_source,
    cover_days,
    45                                                      AS target_cover_days,
    CASE
        WHEN cover_days IS NULL THEN 0
        ELSE CAST(CEIL(GREATEST(velocity_90d * 45 - closing_units, 0)) AS BIGINT)
    END                                                     AS reorder_units,
    CASE
        WHEN cover_days IS NULL THEN 0
        ELSE CAST(CEIL(GREATEST(velocity_90d * 45 - closing_units, 0)) AS BIGINT)
             * stock_value_per_unit
    END                                                     AS reorder_value_EGP,
    CASE
        WHEN cover_days IS NULL THEN 'No demand signal'
        WHEN cover_days < 14 THEN 'Critical (<14d)'
        WHEN cover_days < 30 THEN 'Low (14-30d)'
        WHEN cover_days < 45 THEN 'Below target (30-45d)'
        WHEN cover_days <= 180 THEN 'Adequate (45-180d)'
        ELSE 'Overstock (>180d)'
    END                                                     AS signal,
    CASE
        WHEN cover_days IS NULL THEN 'Review stock, no recent velocity'
        WHEN cover_days < 14 THEN 'Reorder now'
        WHEN cover_days < 30 THEN 'Raise reorder now'
        WHEN cover_days < 45 THEN 'Plan reorder'
        WHEN cover_days <= 180 THEN 'No action'
        ELSE 'Review overstock'
    END                                                     AS action
FROM covered;
