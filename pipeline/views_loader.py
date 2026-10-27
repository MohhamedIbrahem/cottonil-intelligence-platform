"""Apply numbered curated-view SQL files and generate pipeline/VIEW_CATALOG.md.

Every view lives in pipeline/views/<NNN_name>.sql and is applied in ascending file
order (later views may reference earlier ones). The catalog document is regenerated
from VIEWS_META whenever the views are (re)built, so docs stay in lock-step with code
(Constitution IV - traceability).
"""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from pipeline import config

# Substitution constants available to view SQL files (e.g. DATE '{DATA_END_DATE}')
VIEW_CONSTANTS: dict[str, str] = {
    "DATA_END_DATE": config.DATA_END_DATE,
}

# view name -> (grain, key columns, joins / derivation, notes)
VIEWS_META: dict[str, dict[str, str]] = {
    "sales_enriched": {
        "grain": "one row per sales order line",
        "columns": "order_date, year, ym, channel, payment, branch/governorate, customer segment (Guest-safe), category, audience, price/cost, gross/discount/net/margin",
        "derivation": "sales_order_items LEFT JOIN sales_orders JOIN branches JOIN products LEFT JOIN customers",
        "notes": "Transaction spine for every revenue metric. Guest orders (~19%) get customer_segment='Guest' (audit A4).",
    },
    "monthly_sales": {
        "grain": "one row per month",
        "columns": "ym, net, gross_profit, orders, units, active customers, per-channel splits",
        "derivation": "aggregates from sales_enriched",
        "notes": "Powers executive trend + channel mix.",
    },
    "demand_monthly": {
        "grain": "month x product category (incl. the partial current month)",
        "columns": "ym, year, category, units, net, gross profit, orders, customers, avg net price, margin, is_complete_month",
        "derivation": "aggregates from sales_enriched",
        "notes": "96 complete months through 2026-09 plus partial 2026-10; forecast fitting/backtests must filter is_complete_month.",
    },
    "branch_daily": {
        "grain": "branch x day",
        "columns": "orders, customers, units, net, profit, discount",
        "derivation": "aggregates from sales_enriched",
        "notes": "Period-filterable branch metrics (dashboards sum over selected period).",
    },
    "branch_summary": {
        "grain": "one row per branch (all time)",
        "columns": "net, orders, basket avg, profit, margin %, first/last order",
        "derivation": "aggregates from sales_enriched",
        "notes": "All-time profile; period views should use branch_daily.",
    },
    "workforce_monthly": {
        "grain": "branch x month, only branch-months with >=1 payroll record",
        "columns": "paid employees, base/overtime/bonus/deductions/net paid, branch sales/orders/units, sales and payroll per paid employee, labor cost ratio, ever-attached employees",
        "derivation": "raw.payroll JOIN raw.employees aggregated to branch-month; LEFT JOIN branch_daily for sales; roster count from raw.employees",
        "notes": "5,644 branch-months. paid_employees = payroll-covered headcount, not active headcount or FTE. net_paid = base + overtime + bonus - deductions. Branch sales include all channels; no hours/attendance/service data (A16).",
    },
    "product_overview": {
        "grain": "one row per product (all time)",
        "columns": "variants, units, net, profit, first/last order",
        "derivation": "products LEFT JOIN variant counts LEFT JOIN sales aggregates",
        "notes": "Master product profile (Assortment / profitability).",
    },
    "top_products": {
        "grain": "product x month",
        "columns": "units, net, profit, orders",
        "derivation": "aggregates from sales_enriched",
        "notes": "'Top products last month' style questions.",
    },
    "product_monthly": {
        "grain": "product x month",
        "columns": "product/category/audience, units, gross/discount/net, profit, price, discount rate, margin",
        "derivation": "aggregates from sales_enriched",
        "notes": "13,483 selling product-months. All-time product margins cluster at ~38%; use sku_monthly for low-margin alerts (audit A13).",
    },
    "sku_monthly": {
        "grain": "SKU x month",
        "columns": "size/color, units, gross/discount/net, profit, price, discount rate, margin",
        "derivation": "aggregates from sales_enriched LEFT JOIN raw.sku_variants (lookup context)",
        "notes": "66,627 selling SKU-months; margin range ~7.5-56% (audit A13).",
    },
    "channel_monthly": {
        "grain": "month x sales channel",
        "columns": "orders, customers, units, gross/discount/net, profit, AOV, discount rate, margin",
        "derivation": "aggregates from sales_enriched",
        "notes": "291 rows. Only omnichannel history available - no sessions, funnels, carts, app users, or marketplace data.",
    },
    "stock_monthly": {
        "grain": "month x location x category",
        "columns": "closing units/value, stockout risk, location label/governorate",
        "derivation": "monthly_stock enriched with branch/warehouse labels",
        "notes": "Stock base view; raw fields kept as-is (audit A7).",
    },
    "stock_status": {
        "grain": "month x location x category + status bucket",
        "columns": "stock_status in (Low stock / Overstock / In stock)",
        "derivation": "risk >= 0.6 -> Low stock; else top decile units within category-month -> Overstock; else In stock",
        "notes": "Bucket policy documented here (deck p5 style).",
    },
    "stock_latest": {
        "grain": "latest month snapshot of stock_status",
        "columns": "same as stock_status",
        "derivation": "stock_status filtered to max(year_month)",
        "notes": "Dashboard KPI view.",
    },
    "delivery_ops": {
        "grain": "one row per shipment",
        "columns": "order/ship/delivery dates, carrier, status, delivery days, shipping fee, destination governorate, fulfilling branch",
        "derivation": "delivery_shipments JOIN sales_orders (E-commerce only) LEFT JOIN branches; 1:1 order-shipment",
        "notes": "ship_to_governorate is the customer delivery address, not the fulfilling branch governorate. No live tracking.",
    },
    "transfer_ops": {
        "grain": "one row per inventory transfer",
        "columns": "date/status, source warehouse, destination branch/governorate/type, transport cost, lines, SKUs, units, cost per unit",
        "derivation": "inventory_transfers JOIN warehouses JOIN branches; items aggregated per transfer",
        "notes": "transport_cost_EGP is transfer-level and is counted once; summing it never double-counts items.",
    },
    "returns_enriched": {
        "grain": "one row per return",
        "columns": "reason, refund, refund_capped, line net, branch/category context",
        "derivation": "sales_returns LEFT JOIN sales_enriched",
        "notes": "refund_capped = LEAST(refund, line net) per audit A3.",
    },
    "supplier_pos": {
        "grain": "one row per supplier (all time)",
        "columns": "#POs, lines, units, value (A1!), avg lead days, on-time %",
        "derivation": "suppliers JOIN purchase_orders JOIN items; on_time = delivery within 30 days of PO date",
        "notes": "Value column NOT comparable to COGS/revenue (audit A1).",
    },
    "procurement_monthly": {
        "grain": "po month x supplier",
        "columns": "POs, lines, units, value (A1!), avg lead days, on-time rate, partial receipts",
        "derivation": "purchase_orders JOIN purchase_order_items JOIN suppliers, grouped to supplier-month; on_time = delivery_date <= po_date + payment_terms_days",
        "notes": "value_EGP is ABSOLUTE-ONLY (audit A1). On-time uses payment terms because no contractual promised date exists.",
    },
    "customer_rfm": {
        "grain": "one row per customer with >=1 order",
        "columns": "recency, frequency, monetary, quintiles (R/F/M), RFM tier (deck p19 names)",
        "derivation": "orders aggregates as of DATA_END_DATE 2026-10-18; quintiles NTILE(5); label matrix",
        "notes": "Champions / Loyal / Potential Loyalist / Need Attention / At Risk / Churned.",
    },
    "customer_profile": {
        "grain": "one row per cataloged customer",
        "columns": "segment, age band, gov, lifetime orders/value, recency, RFM tier (or 'No purchase')",
        "derivation": "customers LEFT JOIN customer_rfm",
        "notes": "Customer intelligence page + assistant lookups.",
    },
    "customer_clv": {
        "grain": "one row per cataloged customer (85,000), incl. zero-order customers",
        "columns": "lifetime orders/units/net/profit (historical CLV), AOV, margin, recency, tenure, has_purchased, churn_status, is_churn_eligible",
        "derivation": "raw.customers LEFT JOIN sales_enriched lifetime aggregates",
        "notes": "CLV = historical gross profit, not predictive. Churn = no purchase >=365d for tenure >=365d (audit A12); guests excluded from customer metrics (A4).",
    },
    "expansion_gap": {
        "grain": "one row per governorate (21)",
        "columns": "branches (retail / POS-reseller), resident customers/buyers/orders/net sales, branch all-channel and Retail POS sales/orders, per-branch ratios, coverage shares, network-minus-buyer-share gap",
        "derivation": "raw.branches + raw.customers by governorate; resident demand from sales_enriched.customer_governorate_ar; branch demand from sales_enriched.branch_governorate_ar (all channels, plus Retail POS split)",
        "notes": "Residence-based demand proxy, not catchment. 95.2% of identified lines have customer gov != branch gov; branch_id is not geographic. All 21 governorates already have >=1 branch (A17).",
    },
    "wholesale_accounts": {
        "grain": "one row per B2B reseller customer with >=1 order (all time)",
        "columns": "orders, units, net, profit, AOV, margin, first/last order, active months, primary channel, top category, recency bucket, net quartile",
        "derivation": "sales_enriched filtered to customer_segment='B2B reseller', aggregated by customer + customer dimension",
        "notes": "No distributor-account table: accounts are aggregated B2B customers (scope S22). Segment view, not the Wholesale channel.",
    },
    "replenishment_signals": {
        "grain": "latest stock month x location x category (1,472 cells)",
        "columns": "closing units/value, risk, 90-day velocity, cover days, target 45d, reorder units/value, signal, action",
        "derivation": "stock_latest + branch sales velocity (90d) or warehouse outgoing-transfer velocity (90d); reorder = ceil(velocity*45 - closing_units) when cover <45d",
        "notes": "Rules-based heuristic, not an optimiser. Category level only; branches use sales velocity, warehouses use transfers; no lead-time data (audit A14).",
    },
    "campaigns_clean": {
        "grain": "one row per campaign",
        "columns": "spend, impressions, clicks, CTR, budget use %, re-attributed orders/net",
        "derivation": "marketing_campaigns + attribution rebuilt from real orders overlapping window x customer governorate (guests excluded)",
        "notes": "orders_attributed (24.1M) NOT used for revenue math (audit A2).",
    },
}


def apply_views(con: DuckDBPyConnection) -> None:
    """Apply each numbered view SQL file, then refresh the catalog document."""
    files = sorted(config.VIEWS_DIR.glob("*.sql"))
    if not files:
        raise FileNotFoundError(f"No view SQL files found in {config.VIEWS_DIR}")
    for sql_file in files:
        sql = sql_file.read_text(encoding=config.ENCODING).format(**VIEW_CONSTANTS)
        con.execute(sql)
        view_name = sql_file.stem.split("_", 1)[1]
        rows = con.execute(f"SELECT COUNT(*) FROM {config.VIEW_SCHEMA}.{view_name}").fetchone()
        assert rows is not None
        print(f"  view views.{view_name:<20} rows={rows[0]:>9,} ({sql_file.name})")
    _write_catalog_doc()


def _write_catalog_doc() -> None:
    lines = [
        "# VIEW CATALOG (generated - do not edit by hand)",
        "",
        "Auto-generated by `pipeline.views_loader` on every build. Metric definitions live here per",
        "Constitution IV; anomaly policies referenced (A1-A17) are defined in `docs/DATA_AUDIT.md`.",
        "",
    ]
    for view_name, meta in VIEWS_META.items():
        lines += [
            f"## {view_name}",
            f"- **Grain**: {meta['grain']}",
            f"- **Key columns**: {meta['columns']}",
            f"- **Derivation**: {meta['derivation']}",
            f"- **Notes**: {meta['notes']}",
            "",
        ]
    config.CATALOG_DOC.write_text("\n".join(lines), encoding=config.ENCODING)


def installed_views(con: DuckDBPyConnection) -> list[str]:
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = ? ORDER BY 1",
        [config.VIEW_SCHEMA],
    ).fetchall()
    return [r[0] for r in rows]
