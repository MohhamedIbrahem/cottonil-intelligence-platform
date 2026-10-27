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
- Return rate = distinct returned orders in views.returns_enriched / all orders in the period
  (numerator uses return date, denominator uses order date - a period ratio, not a cohort rate).
- Refunds: ALWAYS use refund_capped (audit A3).
- Delivery: views.delivery_ops = one row per shipment (all E-commerce). destination_governorate
  is the customer address. Statuses are only Delivered / Delayed; no live tracking.
- Transfers: views.transfer_ops = one row per transfer; transport_cost_EGP is transfer-level and
  counted once. Open = In transit + Partially received.
- Procurement: views.procurement_monthly = po month x supplier. On-time = item delivery <=
  PO date + payment terms (no contractual promised date). Lead days = delivery - PO date.
- Marketing: spend/impressions/clicks are source fields. attributed_* is rebuilt under A2 from
  real orders in the campaign window x customer governorate; it is directional and non-additive.
  ROAS = attributed_net_real / spend_EGP; CPA = spend_EGP / attributed_orders_real.
- Wholesale: views.wholesale_accounts = B2B reseller SEGMENT (aggregated customers), not the
  Wholesale channel. There is no distributor-account or sell-out table.
- RFM tiers are as-of 2026-10-18 profile facts (do not change with a period filter).
- monthly stock: views.stock_monthly / stock_status / stock_latest; grain is month x location x category.
- stock status buckets: risk >= 0.60 -> 'Low stock'; top decile closing_units -> 'Overstock'; else 'In stock'.
- Demand: views.demand_monthly is month x category; 96 complete months through 2026-09 plus partial
  2026-10. Forecasts fit/backtest on is_complete_month only (A15). Units forecast is much more accurate
  (latest holdout WAPE 3.03%) than net sales (7.27%); the band is an empirical P80 error, not a CI.
- Price: views.sku_monthly is SKU x month with gross/discount/net/profit, avg price, discount rate, margin.
  The within-SKU/month log-log regression shows NO usable elasticity: price coefficient +0.229, within-R2
  0.0002 (A11). Report it as a failed diagnostic; never set prices or claim promo lift from it.
- Channels: views.channel_monthly is month x order channel (Retail POS / E-commerce / Wholesale). It is the
  only omnichannel history; there are no sessions, carts, app users or marketplace feeds.
- Margin: views.product_monthly and views.sku_monthly. Product all-time margins are nearly uniform
  (37.6-39.4%); use SKU-month margin for variation (7.5-55.9%) and the 30% low-margin display flag (A13).
- Replenishment: views.replenishment_signals is latest snapshot x location x category; cover = closing units
  / 90-day daily velocity (branches sales, warehouses outgoing transfers); reorder target 45 days (A14).
  It is a heuristic category-level signal, not a purchase order - no lead time, MOQ or open-PO netting.
- CLV: views.customer_clv has one row per cataloged customer. CLV = historical gross profit, not a forecast.
  Churn = no order for 365+ days with 365+ days tenure; never-purchased/insufficient-history are separate.
  The churn holdout AUC is 0.4995 (no discrimination) - do not rank or target customers from it (A12).
- Workforce: views.workforce_monthly is branch x month, only branch-months with a payroll record (5,644 rows).
  paid_employees = payroll-covered headcount, NOT active headcount or FTE. net_paid = base + overtime + bonus -
  deductions (exact in all 13,210 source rows). labor_cost_ratio = net_paid / branch-attributed sales in the
  same branch-month. Page 18 uses 2023 for the broadest full-year coverage (72/80 branches with 12 months;
  922/960 branch-months); 2018 and 2026 are partial (A16).
- Expansion: views.expansion_gap is one row per governorate (21). resident_* uses the customer address
  (identified customers only; guests excluded); branch_* uses the branch governorate (all channels; POS split =
  Retail POS). All 21 governorates already have >=1 branch. It is a coverage-intensity proxy, not catchment,
  market potential or a site-selection score (A17).

### Data quirks (answer honestly, never paper over)
- A1: purchase-order value in views.supplier_pos and views.procurement_monthly is ABSOLUTE-ONLY -
  never compare against COGS/revenue.
- A2: NEVER use raw columns for marketing attribution; use views.campaigns_clean (attributed_orders_real,
  attributed_net_real). Attribution overlaps across campaigns and is not incremental.
- A3: refunds must use refund_capped (refunds above line value are capped).
- A4: ~19% of orders are guest checkouts with customer_id NULL - they count in revenue, never in customer counts.
- A5: dataset ends 2026-10-18; 'last month' = 2026-09 (last complete month); current calendar month is partial.
- A11: price elasticity is NOT identifiable in this dataset (positive coefficient, within-R2 ~0.0002).
  Say the data show no usable price response; never turn it into pricing advice.
- A12: churn is NOT predictable from the available features (holdout AUC ~0.50, flat deciles).
  Use churn_status descriptively; never present a churn score, ranking or predictive CLV.
- A13: product-level margins are nearly uniform; SKU-month margins carry the variation. The 30%
  low-margin flag is a display threshold, not a policy or a loss claim.
- A14: replenishment is a 45-day cover heuristic at category grain; no lead time, MOQ, shelf life,
  budget or supplier capacity. Never present reorder_units as a purchase order.
- A15: forecasts exclude the partial 2026-10 month; report backtest WAPE and say the band is an
  empirical P80 planning range, not a confidence interval. No causal drivers or SKU forecasts.
- A16: workforce is payroll-covered only: no hours, attendance, FTE, checkout times, tasks, service scores
  or termination dates. The payroll tail (225 paid in 2023-03 falling to 10 in 2026-10) is coverage/tenure
  behaviour, NOT evidence of layoffs. Paid employees is not active headcount; branch sales include
  e-commerce/wholesale orders carrying a branch_id, so sales per paid employee is not hourly productivity.
- A17: expansion_gap is a governorate coverage proxy, not market potential or site selection. No demographics,
  competitors, rent, catchment, cannibalisation, store health or capital cost; every governorate already has a
  branch. 95.2% of identified lines have customer governorate != branch governorate, so resident and branch
  lenses are not reconcilable, and the ranking is mostly a branch-count ranking.
- Dataset scope: Egypt retail (Cottonil). ESG / planogram / loss prevention metrics are NOT in the dataset -
  say so instead of inventing numbers. Returns have no inspection/claims funnel; wholesale has no distributor
  sell-out data; expansion has no market/site inputs (A17) and workforce has no hours/capacity inputs (A16).
"""
