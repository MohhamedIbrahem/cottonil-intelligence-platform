"""Prompt-ready database contract for the assistant (T090).

Built from the live DuckDB (exact column names + types via DESCRIBE) merged with
pipeline.views_loader.VIEWS_META (grain / derivation / notes). The assistant
prompt embeds this so the model can only write valid SQL against real columns,
and the allow-list makes raw facts unavailable on purpose - answers must come
from curated views (Constitution III).
"""

from __future__ import annotations

from functools import lru_cache

import duckdb

from assistant.sql_guard import ALLOWED_RAW_DIMS, ALLOWED_VIEW_NAMES
from pipeline import config
from pipeline.views_loader import VIEWS_META


@lru_cache(maxsize=1)
def _describe() -> dict[str, list[tuple[str, str]]]:
    """Schema-checked views: name -> [(column, duckdb type), ...]."""
    if not config.DB_PATH.exists():
        return {}
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    try:
        out: dict[str, list[tuple[str, str]]] = {}
        for name in sorted(ALLOWED_VIEW_NAMES):
            rows = con.execute(f"DESCRIBE {config.VIEW_SCHEMA}.{name}").fetchall()
            out[name] = [(r[0], r[1]) for r in rows]
        dims: list[tuple[str, str]] = []
        for name in sorted(ALLOWED_RAW_DIMS):
            rows = con.execute(f"DESCRIBE {config.RAW_SCHEMA}.{name}").fetchall()
            dims.extend((f"raw.{name}.{r[0]}", r[1]) for r in rows)
        out["__raw_dims__"] = dims
        return out
    finally:
        con.close()


def schema_text() -> str:
    """Compact schema contract: views grouped with grain/columns + notes + raw dims."""
    described = _describe()
    if not described:
        return "(database not built yet - run `uv run build`)"

    lines: list[str] = ["### Curated views (single source of truth)", ""]
    for name in sorted(ALLOWED_VIEW_NAMES):
        meta = VIEWS_META.get(name, {})
        cols = described.get(name, [])
        col_str = ", ".join(f"{c} {t}" for c, t in cols)
        lines += [
            f"**views.{name}** — grain: {meta.get('grain', '?')}",
            f"  columns: {col_str}",
            f"  derivation: {meta.get('derivation', '?')} | notes: {meta.get('notes', '')}",
            "",
        ]
    dims = described.get("__raw_dims__", [])
    if dims:
        lines += [
            "### Allowed raw dimension tables (lookup only; raw *facts* are NOT queryable)",
            "raw.branches, raw.warehouses, raw.products_catalog, raw.sku_variants, raw.customers,",
            ("raw.suppliers, raw.import_partners, raw.factories, raw.employees "
             "(exact columns via DESCRIBE at runtime; the assistant may still reference these)"),
            "",
        ]
    lines.append(METRIC_NOTES)
    return "\n".join(lines)


METRIC_NOTES = """### Metric definitions (must be respected)
- Net sales = SUM(net_sales) (line-level, after discounts, BEFORE 14% VAT). Orders = COUNT(DISTINCT sales_order_id).
- Gross profit = SUM(gross_profit) (margin_EGP as recorded). AOV = net sales / orders.
- Active customers = COUNT(DISTINCT customer_id) with a non-null id (guests have NULL; audit A4).
- Return rate = orders with >=1 return in views.returns_enriched / all orders in the period.
- RFM tiers are as-of 2026-10-18 profile facts (do not change with a period filter).
- monthly stock: views.stock_monthly / stock_status / stock_latest; grain is month x location x category.
- stock status buckets: risk >= 0.60 -> 'Low stock'; top decile closing_units -> 'Overstock'; else 'In stock'.

### Data quirks (answer honestly, never paper over)
- A1: purchase-order value in views.supplier_pos is ABSOLUTE-ONLY - never compare against COGS/revenue.
- A2: NEVER use raw columns for marketing attribution; use views.campaigns_clean (attributed_orders_real, attributed_net_real).
- A3: refunds must use refund_capped (refunds above line value are capped).
- A4: ~19% of orders are guest checkouts with customer_id NULL - they count in revenue, never in customer counts.
- A5: dataset ends 2026-10-18; 'last month' = 2026-09 (last complete month); current calendar month is partial.
- Dataset scope: Egypt retail (Cottonil). ESG / planogram / loss prevention / store-expansion metrics
  are NOT in the dataset - say so instead of inventing numbers.
"""
