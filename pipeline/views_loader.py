"""Apply numbered curated-view SQL files and generate pipeline/VIEW_CATALOG.md.

Every view lives in pipeline/views/<NNN_name>.sql and is applied in ascending file
order (later views may reference earlier ones). The catalog document is regenerated
from VIEWS_META whenever the views are (re)built, so docs stay in lock-step with code
(Constitution IV - traceability).
"""

from __future__ import annotations

from pathlib import Path

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
        "Constitution IV; anomaly policies referenced (A1-A7) are defined in `docs/DATA_AUDIT.md`.",
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


def view_file_path(view_name: str) -> Path:
    matches = list(config.VIEWS_DIR.glob(f"*_{view_name}.sql"))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected exactly one SQL file for view '{view_name}'")
    return matches[0]
