"""Data-quality gate for the Cottonil pipeline (Constitution IV / tasks T012-T013).

Checks are split into:
- FK_ORPHANS: referential-integrity checks, each MUST return 0.
- RECONCILIATION: financial-mechanics checks, each MUST return 0.
- WARNINGS: documented anomalies that MUST NOT fail the build (audit A1-A3, A4).

Usage:
    uv run checks
Exit codes: 0 = all gates green, 1 = at least one failing gate, 2 = database missing.
"""

from __future__ import annotations

import sys

import duckdb
from duckdb import DuckDBPyConnection

from pipeline import config

# name -> SQL returning a count that MUST be 0
FK_ORPHANS: list[tuple[str, str]] = [
    ("sales_order_items -> sales_orders", """
        SELECT COUNT(*) FROM raw.sales_order_items i
        LEFT JOIN raw.sales_orders o USING (sales_order_id)
        WHERE o.sales_order_id IS NULL"""),
    ("sales_order_items -> sku_variants", """
        SELECT COUNT(*) FROM raw.sales_order_items i
        LEFT JOIN raw.sku_variants s USING (sku_id) WHERE s.sku_id IS NULL"""),
    ("sales_order_items -> products_catalog", """
        SELECT COUNT(*) FROM raw.sales_order_items i
        LEFT JOIN raw.products_catalog p USING (product_id) WHERE p.product_id IS NULL"""),
    ("sales_orders -> branches", """
        SELECT COUNT(*) FROM raw.sales_orders o
        LEFT JOIN raw.branches b ON b.branch_id = o.branch_id WHERE b.branch_id IS NULL"""),
    ("sales_orders -> customers (non-guest)", """
        SELECT COUNT(*) FROM raw.sales_orders o
        WHERE o.customer_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM raw.customers c
                          WHERE c.customer_id = o.customer_id)"""),
    ("sales_payments -> sales_orders", """
        SELECT COUNT(*) FROM raw.sales_payments p
        LEFT JOIN raw.sales_orders o USING (sales_order_id) WHERE o.sales_order_id IS NULL"""),
    ("sales_returns -> sales_orders", """
        SELECT COUNT(*) FROM raw.sales_returns r
        LEFT JOIN raw.sales_orders o ON o.sales_order_id = r.sales_order_id
        WHERE o.sales_order_id IS NULL"""),
    ("sales_returns -> sales_order_lines", """
        SELECT COUNT(*) FROM raw.sales_returns r
        LEFT JOIN raw.sales_order_items i ON i.sales_line_id = r.sales_line_id
        WHERE i.sales_line_id IS NULL"""),
    ("sales_returns -> sku_variants", """
        SELECT COUNT(*) FROM raw.sales_returns r
        LEFT JOIN raw.sku_variants s USING (sku_id) WHERE s.sku_id IS NULL"""),
    ("delivery_shipments -> sales_orders", """
        SELECT COUNT(*) FROM raw.delivery_shipments d
        LEFT JOIN raw.sales_orders o USING (sales_order_id) WHERE o.sales_order_id IS NULL"""),
    ("inventory_transfers -> source warehouses", """
        SELECT COUNT(*) FROM raw.inventory_transfers t
        LEFT JOIN raw.warehouses w ON w.warehouse_id = t.source_warehouse_id
        WHERE w.warehouse_id IS NULL"""),
    ("inventory_transfers -> destination branches", """
        SELECT COUNT(*) FROM raw.inventory_transfers t
        LEFT JOIN raw.branches b ON b.branch_id = t.destination_branch_id
        WHERE b.branch_id IS NULL"""),
    ("inventory_transfer_items -> transfers", """
        SELECT COUNT(*) FROM raw.inventory_transfer_items i
        LEFT JOIN raw.inventory_transfers t USING (transfer_id) WHERE t.transfer_id IS NULL"""),
    ("inventory_transfer_items -> sku_variants", """
        SELECT COUNT(*) FROM raw.inventory_transfer_items i
        LEFT JOIN raw.sku_variants s USING (sku_id) WHERE s.sku_id IS NULL"""),
    ("purchase_orders -> suppliers", """
        SELECT COUNT(*) FROM raw.purchase_orders p
        LEFT JOIN raw.suppliers s ON s.supplier_id = p.supplier_id WHERE s.supplier_id IS NULL"""),
    ("purchase_orders -> receiving warehouses", """
        SELECT COUNT(*) FROM raw.purchase_orders p
        LEFT JOIN raw.warehouses w ON w.warehouse_id = p.receiving_warehouse_id
        WHERE w.warehouse_id IS NULL"""),
    ("purchase_order_items -> purchase_orders", """
        SELECT COUNT(*) FROM raw.purchase_order_items i
        LEFT JOIN raw.purchase_orders p USING (po_id) WHERE p.po_id IS NULL"""),
    ("purchase_order_items -> sku_variants", """
        SELECT COUNT(*) FROM raw.purchase_order_items i
        LEFT JOIN raw.sku_variants s USING (sku_id) WHERE s.sku_id IS NULL"""),
    ("import_shipments -> partners", """
        SELECT COUNT(*) FROM raw.import_shipments s
        LEFT JOIN raw.import_partners p USING (import_partner_id) WHERE p.import_partner_id IS NULL"""),
    ("import_shipments -> destination warehouses", """
        SELECT COUNT(*) FROM raw.import_shipments s
        LEFT JOIN raw.warehouses w ON w.warehouse_id = s.destination_warehouse_id
        WHERE w.warehouse_id IS NULL"""),
    ("employees -> branches", """
        SELECT COUNT(*) FROM raw.employees e
        LEFT JOIN raw.branches b ON b.branch_id = e.branch_id WHERE b.branch_id IS NULL"""),
    ("payroll -> employees", """
        SELECT COUNT(*) FROM raw.payroll p
        LEFT JOIN raw.employees e ON e.employee_id = p.employee_id WHERE e.employee_id IS NULL"""),
    ("operating_expenses -> branch or warehouse", """
        SELECT COUNT(*) FROM raw.operating_expenses x
        WHERE NOT EXISTS (SELECT 1 FROM raw.branches b WHERE b.branch_id = x.branch_or_department_id)
          AND NOT EXISTS (SELECT 1 FROM raw.warehouses w
                          WHERE w.warehouse_id = x.branch_or_department_id)"""),
    ("monthly_stock -> branch or warehouse", """
        SELECT COUNT(*) FROM raw.monthly_stock s
        WHERE NOT EXISTS (SELECT 1 FROM raw.branches b WHERE b.branch_id = s.stock_location_id)
          AND NOT EXISTS (SELECT 1 FROM raw.warehouses w
                          WHERE w.warehouse_id = s.stock_location_id)"""),
    ("sales_payments single-payment-per-order", """
        SELECT COUNT(*) - COUNT(DISTINCT sales_order_id) FROM raw.sales_payments"""),
    ("sku_variants -> products_catalog", """
        SELECT COUNT(*) FROM raw.sku_variants v
        LEFT JOIN raw.products_catalog p USING (product_id) WHERE p.product_id IS NULL"""),
    ("catalog reference covers all canonical products", """
        SELECT COUNT(*) FROM raw.products_catalog p
        WHERE NOT EXISTS (SELECT 1 FROM raw.catalog_reference r WHERE r.product_id = p.product_id)"""),
]

# name -> SQL returning count of violating rows that MUST be 0
RECONCILIATION: list[tuple[str, str]] = [
    ("orders: gross - discount = net_before_tax", """
        SELECT COUNT(*) FROM raw.sales_orders
        WHERE ABS(gross_EGP - discount_EGP - net_before_tax_EGP) > 0.005"""),
    ("orders: tax = 14% of net (tolerance 0.1%)", """
        SELECT COUNT(*) FROM raw.sales_orders
        WHERE ABS(tax_EGP - net_before_tax_EGP * 0.14) > ABS(net_before_tax_EGP) * 0.001"""),
    ("orders: paid_total = net + tax", """
        SELECT COUNT(*) FROM raw.sales_orders
        WHERE ABS(paid_total_EGP - net_before_tax_EGP - tax_EGP) > 0.01"""),
    ("orders: items_count = item-line count", """
        SELECT COUNT(*) FROM raw.sales_orders o
        JOIN (SELECT sales_order_id, COUNT(*) AS lines
              FROM raw.sales_order_items GROUP BY sales_order_id) l
          ON l.sales_order_id = o.sales_order_id
        WHERE o.items_count <> l.lines"""),
    ("orders vs items: totals reconcile (exact sums)", """
        SELECT CASE WHEN ABS(
            (SELECT SUM(net_before_tax_EGP) FROM raw.sales_orders)
          - (SELECT SUM(net_line_EGP) FROM raw.sales_order_items)
        ) > 0.01 THEN 1 ELSE 0 END"""),
    ("purchase_order_items: line_cost = qty * unit_cost", """
        SELECT COUNT(*) FROM raw.purchase_order_items
        WHERE ABS(line_cost_EGP - quantity * unit_cost_EGP) > 0.01"""),
    ("purchase_orders: subtotal = line total", """
        SELECT COUNT(*) FROM raw.purchase_orders p
        JOIN (SELECT po_id, SUM(line_cost_EGP) AS line_total
              FROM raw.purchase_order_items GROUP BY po_id) l USING (po_id)
        WHERE ABS(p.po_subtotal_EGP - l.line_total) > 0.01"""),
]


def run_checks(con: DuckDBPyConnection) -> tuple[list[tuple[str, int]], list[tuple[str, str]]]:
    """Run all gates. Returns (failures, warnings). Each failure is (name, offending_count)."""
    failures: list[tuple[str, int]] = []
    warnings: list[tuple[str, str]] = []

    for name, sql in FK_ORPHANS + RECONCILIATION:
        (count,) = con.execute(sql).fetchone()
        if count != 0:
            failures.append((name, count))

    # Documented anomalies -> warnings, never gates (audit policies A1-A3)
    (po_total,) = con.execute("SELECT SUM(po_subtotal_EGP) FROM raw.purchase_orders").fetchone()
    (sales_total,) = con.execute("SELECT SUM(net_before_tax_EGP) FROM raw.sales_orders").fetchone()
    ratio = po_total / sales_total if sales_total else float("inf")
    msg_a1 = (
        f"PO total {po_total:,.0f} EGP is {ratio:.1f}x all-time net sales "
        f"({sales_total:,.0f} EGP). Procurement metrics are absolute-only "
        "(never reconciled against COGS/revenue)."
    )
    warnings.append(("A1 purchase-order scale", msg_a1))

    (report_orders,) = con.execute(
        "SELECT SUM(orders_attributed) FROM raw.marketing_campaigns"
    ).fetchone()
    (real_orders,) = con.execute("SELECT COUNT(*) FROM raw.sales_orders").fetchone()
    msg_a2 = (
        f"orders_attributed sums to {report_orders:,.0f} vs {real_orders:,.0f} real orders - "
        "excluded from revenue math; attribution rebuilt in views.campaigns_clean."
    )
    warnings.append(("A2 marketing attribution", msg_a2))

    (over_limit,) = con.execute("""
        SELECT COUNT(*) FROM raw.sales_returns r
        JOIN raw.sales_order_items i ON i.sales_line_id = r.sales_line_id
        WHERE r.refund_amount_EGP > i.net_line_EGP
    """).fetchone()
    msg_a3 = (
        f"{over_limit:,} refunds exceed their line net value - capped in "
        "views.returns_enriched (refund_capped)."
    )
    warnings.append(("A3 refund overshoot", msg_a3))

    (guests,) = con.execute(
        "SELECT COUNT(*) FROM raw.sales_orders WHERE customer_id IS NULL"
    ).fetchone()
    msg_a4 = (
        f"{guests:,} orders ({guests / real_orders:.1%} of {real_orders:,}) have no "
        "customer_id - counted as 'Guest' segment in views, excluded from customer metrics."
    )
    warnings.append(("A4 guest orders", msg_a4))

    (pub_only,) = con.execute("""
        SELECT COUNT(*) FROM raw.catalog_reference r
        WHERE NOT EXISTS (SELECT 1 FROM raw.products_catalog p
                          WHERE p.product_id = r.product_id)
    """).fetchone()
    msg_a9 = (
        f"{pub_only} of 238 public-reference rows use a separate 'PUBxxxx' id "
        "namespace (website-only products, not in the sales catalog). "
        "Canonical sales products (139) all appear in the reference (gated); "
        "PUB rows are enrichment-only, never sales-joinable."
    )
    warnings.append(("A9 public-catalog extras", msg_a9))

    return failures, warnings


def _print_report(failures, warnings) -> None:
    print("Data-quality gate")
    print("=" * 60)
    print(f"Gates run: {len(FK_ORPHANS) + len(RECONCILIATION)}  "
          f"(FK/lookups {len(FK_ORPHANS)}, reconciliations {len(RECONCILIATION)})")
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for name, count in failures:
            print(f"  [FAIL] {name}: {count:,} offending rows (expected 0)")
    else:
        print("All gates PASS (0 offending rows in every integrity/reconciliation check).")
    print("-" * 60)
    print("Documented anomaly warnings (non-blocking):")
    for name, message in warnings:
        print(f"  [warn] {name}: {message}")


def main() -> int:
    db_path = config.DB_PATH
    if not db_path.exists():
        print(f"Database not found: {db_path}", file=sys.stderr)
        print("Run the pipeline first:  uv run build", file=sys.stderr)
        return 2
    con = duckdb.connect(str(db_path), read_only=True)
    failures, warnings = run_checks(con)
    con.close()
    _print_report(failures, warnings)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
