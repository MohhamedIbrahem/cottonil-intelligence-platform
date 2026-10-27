-- View: expansion_gap
-- Grain: one row per governorate (21)
-- Key columns: branches (retail / POS-reseller), resident customers/buyers/orders/net sales,
--              branch all-channel and Retail POS orders/net sales, per-branch ratios, coverage
--              shares and the network-minus-buyer-share gap.
-- Derivation: raw.branches + raw.customers aggregated by governorate; resident demand from
--             sales_enriched.customer_governorate_ar (identified customers only); branch demand
--             from sales_enriched.branch_governorate_ar (all channels), with a Retail POS split.
-- Notes: residence-based demand, not catchment. Branch_id is not geographic: 95.2% of identified
--        order lines have a customer governorate different from the branch governorate. Every
--        governorate already has >=1 branch. No demographics, competitors, rent, cannibalisation,
--        store health, lease or capital-cost data exist (audit A17).
CREATE OR REPLACE VIEW views.expansion_gap AS
WITH branches AS (
    SELECT
        governorate_ar,
        COUNT(*)                                            AS branches,
        COUNT(*) FILTER (WHERE retail_location_type = 'Retail branch') AS retail_branches,
        COUNT(*) FILTER (WHERE retail_location_type = 'Point of sale / reseller') AS reseller_pos_branches
    FROM raw.branches
    GROUP BY 1
),
customers AS (
    SELECT governorate_ar, COUNT(*)                         AS customers
    FROM raw.customers
    GROUP BY 1
),
resident AS (
    SELECT
        customer_governorate_ar                             AS governorate_ar,
        COUNT(DISTINCT customer_id)                         AS resident_buyers,
        COUNT(DISTINCT sales_order_id)                      AS resident_orders,
        SUM(net_sales)                                      AS resident_net_sales
    FROM views.sales_enriched
    WHERE customer_id IS NOT NULL
    GROUP BY 1
),
branch_all AS (
    SELECT
        branch_governorate_ar                               AS governorate_ar,
        COUNT(DISTINCT sales_order_id)                      AS branch_orders,
        SUM(net_sales)                                      AS branch_net_sales
    FROM views.sales_enriched
    GROUP BY 1
),
branch_pos AS (
    SELECT
        branch_governorate_ar                               AS governorate_ar,
        COUNT(DISTINCT sales_order_id)                      AS pos_orders,
        SUM(net_sales)                                      AS pos_net_sales
    FROM views.sales_enriched
    WHERE sales_channel = 'Retail POS'
    GROUP BY 1
),
totals AS (
    SELECT
        (SELECT COUNT(*) FROM raw.branches)                              AS total_branches,
        (SELECT COUNT(*) FROM raw.customers)                             AS total_customers,
        (SELECT COUNT(DISTINCT customer_id) FROM views.sales_enriched
         WHERE customer_id IS NOT NULL)                                  AS total_buyers,
        (SELECT SUM(net_sales) FROM views.sales_enriched
         WHERE customer_id IS NOT NULL)                                  AS total_resident_net_sales,
        (SELECT SUM(net_sales) FROM views.sales_enriched
         WHERE sales_channel = 'Retail POS')                             AS total_pos_net_sales
)
SELECT
    b.governorate_ar,
    b.branches,
    b.retail_branches,
    b.reseller_pos_branches,
    c.customers,
    r.resident_buyers,
    r.resident_buyers::DOUBLE / NULLIF(c.customers, 0)      AS buyer_penetration,
    r.resident_orders,
    r.resident_orders::DOUBLE / NULLIF(r.resident_buyers, 0) AS orders_per_buyer,
    r.resident_net_sales,
    r.resident_net_sales / NULLIF(r.resident_buyers, 0)     AS resident_net_sales_per_buyer,
    ba.branch_orders,
    ba.branch_net_sales,
    bp.pos_orders,
    bp.pos_net_sales,
    r.resident_buyers::DOUBLE / b.branches                  AS resident_buyers_per_branch,
    r.resident_net_sales / b.branches                       AS resident_net_sales_per_branch,
    bp.pos_net_sales / b.branches                           AS pos_net_sales_per_branch,
    b.branches::DOUBLE / t.total_branches                   AS network_share,
    c.customers::DOUBLE / t.total_customers                 AS customer_share,
    r.resident_buyers::DOUBLE / t.total_buyers              AS buyer_share,
    r.resident_net_sales / NULLIF(t.total_resident_net_sales, 0) AS resident_sales_share,
    bp.pos_net_sales / NULLIF(t.total_pos_net_sales, 0)     AS pos_sales_share,
    (b.branches::DOUBLE / t.total_branches
        - r.resident_buyers::DOUBLE / t.total_buyers) * 100 AS network_minus_buyer_share_pp
FROM branches b
JOIN customers c USING (governorate_ar)
JOIN resident r USING (governorate_ar)
JOIN branch_all ba USING (governorate_ar)
JOIN branch_pos bp USING (governorate_ar)
CROSS JOIN totals t;
