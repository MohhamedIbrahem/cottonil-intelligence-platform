"""Cottonil Intelligence Platform - landing page (app shell, T033).

Home doubles as the platform's brand, coverage and data-policy screen.
Dashboard pages live in app/pages/ and are auto-registered by Streamlit.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Multipage bootstrap: allow `from app import ...` whether this file runs as
# app/Home.py (parents[1] = repo root) or as app/pages/*.py (parents[2]).
_FILE = Path(__file__).resolve()
_ROOT = _FILE.parents[2] if _FILE.parent.name == "pages" else _FILE.parents[1]
sys.path.insert(0, str(_ROOT))

import streamlit as st

from app import data, theme
from app.filters import DATA_END, render_period_selector
from pipeline import config

st.set_page_config(
    page_title="Cottonil Intelligence · Business Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.apply_theme()

# The shared reporting-period control is visible on the landing page too.
render_period_selector()

if not config.DB_PATH.exists():
    theme.hero(
        "One read-only source of truth for the whole business.",
        "The DuckDB database has not been built yet. Build it first, then reload this page.",
        eyebrow="Cottonil Intelligence Platform",
        meta=(("Setup required", "warn"),),
    )
    st.code("uv run build", language="bash")
    st.stop()

# --- headline numbers straight from the database ------------------------------
_head = data.q(
    "SELECT SUM(net_sales) AS net, SUM(orders) AS orders, COUNT(*) AS months "
    "FROM views.monthly_sales"
).iloc[0]
_dims = data.q(
    "SELECT (SELECT COUNT(*) FROM views.customer_profile) AS customers, "
    "       (SELECT COUNT(*) FROM views.customer_rfm)    AS buyers, "
    "       (SELECT COUNT(*) FROM views.branch_summary)  AS branches, "
    "       (SELECT COUNT(DISTINCT governorate_ar) FROM views.branch_summary) AS governorates"
).iloc[0]

theme.hero(
    "Decision-ready analytics for every Cottonil function.",
    "Sales, branches, inventory, customers, supply chain, procurement, returns, "
    "marketing, wholesale, forecasting, pricing, omnichannel, profitability, "
    "replenishment, CLV, workforce and expansion - grounded in one read-only dataset "
    "and queryable in Arabic or English through the assistant.",
    eyebrow="Cottonil Intelligence Platform",
    meta=(
        (f"Data through {DATA_END.isoformat()}", "good"),
        ("EGP", "neutral"),
        ("Read-only", "neutral"),
        ("19 dashboards", "neutral"),
    ),
)

theme.section_header(
    "Company at a glance",
    "All-time figures from the curated views; every dashboard below uses the same source.",
    eyebrow="Overview",
)

c1, c2, c3, c4 = st.columns(4)
with c1:
    theme.kpi_card(
        "Net sales · all time",
        theme.fmt_egp(float(_head.net)),
        sub=f"excl. 14% VAT · {float(_head.months):,.0f} months of data",
    )
with c2:
    theme.kpi_card(
        "Orders · all time",
        theme.fmt_int(float(_head.orders)),
        sub="line-level spine: views.sales_enriched",
    )
with c3:
    theme.kpi_card(
        "Customers",
        theme.fmt_int(float(_dims.customers)),
        sub=f"{theme.fmt_int(float(_dims.buyers))} with ≥1 order "
        f"({float(_dims.buyers) / float(_dims.customers):.0%}) - rest are catalog-only",
    )
with c4:
    theme.kpi_card(
        "Branches",
        theme.fmt_int(float(_dims.branches)),
        sub=f"across {int(_dims.governorates)} governorates",
    )

st.divider()

# --- dashboard navigation ------------------------------------------------------
theme.section_header(
    "Explore the platform",
    "Nineteen dashboards, grouped by the questions they answer. Open any page from "
    "the sidebar; the reporting-period control follows you across the app.",
    eyebrow="Dashboards",
)

_groups = [
    (
        "Core performance",
        "The board view and the commercial, stock and customer deep dives.",
        [
            (
                "Executive Overview",
                "Net sales, profit, orders, active customers and return rate - the board view.",
                "deck p.2",
                "Phase 3",
            ),
            (
                "Sales Performance",
                "Trends, channel mix, category mix and discount effect.",
                "deck p.3",
                "Phase 4",
            ),
            (
                "Branch & Governorate",
                "Store league table, governorate heat and delivery performance.",
                "deck p.4",
                "Phase 5",
            ),
            (
                "Inventory & Stock",
                "Stock value, cover, stockout risk and top catalog SKUs.",
                "deck p.5-6",
                "Phase 6",
            ),
            (
                "Customers & RFM",
                "Segments, RFM tiers, repeat behavior and governorate spread.",
                "deck p.7,19",
                "Phase 7",
            ),
            (
                "AI Assistant",
                "Ask in Arabic or English; answers grounded in read-only SQL.",
                "deck p.23",
                "Phase 9",
            ),
        ],
    ),
    (
        "Operations",
        "Physical flow, supplier performance, returns and commercial programmes.",
        [
            (
                "Supply Chain & Logistics",
                "Shipment status, carrier comparison, lead times and transfer pipeline.",
                "deck p.8",
                "Feature 002",
            ),
            (
                "Procurement & Suppliers",
                "Supplier scorecards, lead times, on-time proxy and material mix (A1).",
                "deck p.9",
                "Feature 002",
            ),
            (
                "Returns & Quality Control",
                "Return-rate trends, reason mix, refund analysis and defect claims.",
                "deck p.10",
                "Feature 002",
            ),
            (
                "Marketing ROI & Campaigns",
                "Spend, CTR, ROAS, CPA and budget use with rebuilt attribution (A2).",
                "deck p.15",
                "Feature 002",
            ),
            (
                "Wholesale & Distributors",
                "Wholesale channel, B2B accounts, value, recency and concentration.",
                "deck p.22",
                "Feature 002",
            ),
        ],
    ),
    (
        "Planning & growth",
        "Forward-looking views built on explicit assumptions and visible error.",
        [
            (
                "Demand Forecast",
                "Category demand baseline, 6-month forecast and rolling-origin backtest (A15).",
                "deck p.7",
                "Feature 003",
            ),
            (
                "Price & Promotion",
                "Discount depth, margin link and within-SKU price-response test (A11).",
                "deck p.13",
                "Feature 003",
            ),
            (
                "Omnichannel (Lite)",
                "Channel mix, AOV, margin, returns and observed cross-channel customers.",
                "deck p.14",
                "Feature 003",
            ),
            (
                "Product Profitability",
                "SKU-month margin variation, low-margin alerts and top profit products (A13).",
                "deck p.16",
                "Feature 003",
            ),
            (
                "Smart Replenishment",
                "45-day cover rule on the latest stock snapshot and reorder priorities (A14).",
                "deck p.18",
                "Feature 003",
            ),
        ],
    ),
    (
        "Advanced analytics",
        "Customer value, people and network questions with their limits stated.",
        [
            (
                "CLV & Churn",
                "Historical CLV concentration, churn status and churn holdout test (A12).",
                "deck p.19",
                "Feature 003",
            ),
            (
                "Workforce Productivity",
                "Payroll-covered headcount, labor cost ratio and branch payroll detail (A16).",
                "deck p.17",
                "Feature 004",
            ),
            (
                "Store Expansion (Gap Proxy)",
                "Governorate coverage intensity and resident demand vs branch POS (A17).",
                "deck p.12",
                "Feature 004",
            ),
        ],
    ),
]

for group, description, items in _groups:
    theme.section_header(group, description)
    for start in range(0, len(items), 3):
        row = items[start:start + 3]
        cols = st.columns(3)
        for col, (name, desc, page_ref, phase) in zip(cols, row, strict=False):
            with col:
                theme.dashboard_card(
                    name,
                    desc,
                    kicker=f"{page_ref} · {phase}",
                )
    st.write("")

st.caption(
    "25 source tables · 26 curated views · 19 dashboards · monthly snapshots from "
    f"Oct 2018 to {DATA_END.isoformat()} · all figures in EGP."
)

# --- data notes (FR-012 pattern used on every page later) ----------------------
with st.expander("About the data, coverage and policies", expanded=False):
    left, right = st.columns((1, 1.4))
    with left:
        st.markdown("##### Coverage")
        st.markdown(
            f"- **Source**: 25 CSV tables loaded into the `raw` schema.\n"
            f"- **Curated layer**: 26 `views.*` objects; every figure on every "
            f"dashboard comes from this layer.\n"
            f"- **Window**: monthly snapshots Oct 2018 to {DATA_END.isoformat()}; "
            "the last complete month is Sep 2026.\n"
            "- **Dimensions**: 80 branches, 21 governorates and the full customer "
            "catalog.\n"
            "- **Currency**: EGP everywhere (Constitution VII)."
        )
    with right:
        st.markdown("##### Policies and known limits")
        st.markdown(
            "- **Single source of truth**: `data/cottonil.duckdb`, built from the "
            "25 source CSVs; the app opens it read-only and can never mutate it.\n"
            "- **Known quirks are disclosed, not hidden**: guest checkout share "
            "(audit A4), marketing-attribution rebuild (A2), refunds capped at line "
            "value (A3), procurement figures kept absolute-only (A1).\n"
            "- **Weak or failed model signals stay visible**: price response has no "
            "usable elasticity (A11) and the churn holdout does not discriminate "
            "(A12); forecast, margin and replenishment caveats are A15, A13 and A14.\n"
            "- **Coverage limits**: workforce is payroll-covered only (A16) and "
            "expansion is a coverage-intensity proxy with no market inputs (A17).\n"
            "- **Full audit trail**: `docs/DATA_AUDIT.md` and "
            "`pipeline/VIEW_CATALOG.md`."
        )
