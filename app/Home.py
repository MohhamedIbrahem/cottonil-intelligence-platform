"""Cottonil Business Assistant - landing page (app shell, T033).

Home doubles as the app's brand + data-status screen. Dashboard pages live in
app/pages/ and are auto-registered by Streamlit multipage.
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
    page_title="Cottonil · Business Assistant",
    page_icon="🧵",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.apply_theme()

# --- sidebar brand + the shared reporting-period control ---------------------
st.sidebar.markdown("### 🧵 COTTONIL\n:gray[Business Assistant · v0.1]")
render_period_selector()  # shared sidebar control; pages call the same helper

st.markdown("# 🧵 Cottonil Business Assistant")
st.markdown(
    "One place to read the company dataset: sales, branches, inventory, "
    "customers - plus an AI assistant in later phases. "
    f":gray[All figures in EGP · data through **{DATA_END.isoformat()}** · Constitution: real data only.]"
)

# --- headline numbers straight from the database ------------------------------
if not config.DB_PATH.exists():
    st.warning(
        "DuckDB database not found yet. Build it first:\n\n"
        "```\nuv run build\n```",
        icon="🗃️",
    )
    st.stop()

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

c1, c2, c3, c4 = st.columns(4)
with c1:
    theme.kpi_card(
        "Net sales · all time",
        theme.fmt_egp(float(_head.net)),
        sub=f"excl. 14% VAT \u00b7 {float(_head.months):,.0f} months of data",
    )
with c2:
    theme.kpi_card("Orders · all time", theme.fmt_int(float(_head.orders)),
                   sub="line-level spine: views.sales_enriched")
with c3:
    theme.kpi_card(
        "Customers",
        theme.fmt_int(float(_dims.customers)),
        sub=f"{theme.fmt_int(float(_dims.buyers))} with \u22651 order "
            f"({float(_dims.buyers) / float(_dims.customers):.0%}) - rest are catalog-only",
    )
with c4:
    theme.kpi_card("Branches", theme.fmt_int(float(_dims.branches)),
                   sub=f"across {int(_dims.governorates)} governorates")

st.divider()

# --- roadmap cards (mirror of docs/DASHBOARD_SCOPE_MATRIX.md) ------------------
st.markdown("#### Dashboards")
_dashboards = [
    ("📊", "Executive Overview", "Net sales, profit, orders, active customers, return rate - the board view.", "deck p.2", "Phase 3"),
    ("💰", "Sales Performance", "Trends, channel mix, category mix, discount effect.", "deck p.3", "Phase 4"),
    ("🏬", "Branch & Governorate", "Store league table, governorate heat, delivery performance.", "deck p.4", "Phase 5"),
    ("📦", "Inventory & Stock", "Stock value, cover, stockout risk, top catalog SKUs.", "deck p.5-6", "Phase 6"),
    ("👥", "Customers & RFM", "Segments, RFM tiers, repeat behavior, governorate spread.", "deck p.7,19", "Phase 7"),
    ("🤖", "AI Assistant", "Ask in Arabic or English; answers grounded in read-only SQL.", "deck p.23", "Phase 9"),
]
for _row in (_dashboards[0:3], _dashboards[3:6]):
    cols = st.columns(3)
    for col, (emoji, name, desc, page_ref, phase) in zip(cols, _row, strict=True):
        with col:
            st.markdown(
                f'<div class="cottonil-kpi">'
                f'<div class="cpi-title">{page_ref} · {phase}</div>'
                f'<div class="cpi-value" style="font-size:1.15rem">{emoji} {name}</div>'
                f'<div class="cpi-sub" style="margin-top:6px">{desc}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

# --- data notes (FR-012 pattern used on every page later) ----------------------
with st.expander("About this app - data & policies", expanded=False):
    st.markdown(
        "- **Single source of truth**: `data/cottonil.duckdb` built from the 25 source CSVs; "
        "every number on screen comes from the 14 curated `views.*` (see "
        "`pipeline/VIEW_CATALOG.md`).\n"
        "- **Read-only**: the app opens the database read-only; it can never mutate data.\n"
        "- **Known data quirks are disclosed, not hidden**: guest checkout share "
        "(audit A4), marketing-attribution rebuild (A2), refunds capped at line value (A3), "
        "procurement figures kept absolute-only (A1). Full list: "
        "`docs/DATA_AUDIT.md`.\n"
        f"- **Coverage**: monthly snapshots Oct 2018 \u2192 Oct 2026; last complete month = "
        f"Sep 2026; dataset ends {DATA_END.isoformat()}.\n"
        "- **Currency**: EGP everywhere (Constitution VII)."
    )
