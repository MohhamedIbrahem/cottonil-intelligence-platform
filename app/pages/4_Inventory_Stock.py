"""Inventory & Stock (deck p.5-6) - warehouse/branch stock health.

US5 / tasks T070-T074. Snapshot KPIs always come from the LATEST month in the
dataset (views.stock_latest = the last snapshot); the trend follows the sidebar
period like every other page. Audit A7 applies: stock-to-sales scale is
internally consistent, no adjustment.
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import data, theme
from app.filters import DATA_END, render_period_selector

st.set_page_config(
    page_title="Inventory & Stock · Cottonil",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.apply_theme()

start, end, label, _ = render_period_selector()

theme.page_header(
    "Inventory & Stock",
    f"Trend window: **{label}** · snapshot KPIs below use the **latest stock month** "
    f"(dataset ends {DATA_END.isoformat()}) · audit A7 scale policy",
    eyebrow="Operations",
    badges=('Latest snapshot',),
)

# ---------------------------------------------------------------- KPIs (T070) --
latest_month = data.scalar("SELECT MAX(year_month) FROM views.stock_latest")
snap = data.q(
    """
    SELECT SUM(closing_units) AS units, SUM(closing_stock_value) AS value_egp,
           COUNT(*) AS cells, COUNT(DISTINCT stock_location_id) AS locations
    FROM views.stock_latest
""").iloc[0]
at_risk = data.scalar(
    "SELECT COUNT(*) FROM views.stock_latest WHERE stockout_risk_score >= 0.70"
) or 0
low_cells = data.scalar(
    "SELECT COUNT(*) FROM views.stock_latest WHERE stock_status = 'Low stock'"
) or 0

k_cols = st.columns(4)
for col, (title, value, sub) in zip(
    k_cols,
    [
        ("Stock units", theme.fmt_int(float(snap.units)), f"snapshot {latest_month}"),
        ("Stock value", theme.fmt_egp(float(snap.value_egp)), f"closing value, {latest_month}"),
        ("At-risk locations", theme.fmt_pct(int(at_risk) / max(int(snap.cells), 1)),
         f"risk \u22650.70 · {at_risk} of {int(snap.cells)} location×category cells"),
        ("Low-stock cells", f"{int(low_cells)}", "view bucket policy (risk \u22650.60)"),
    ],
    strict=True,
):
    with col:
        theme.kpi_card(title, value, sub=sub)

st.divider()

# ------------------------------------------------------------ trend (T071) --
ym_start = pd.Period(start, freq="M").strftime("%Y-%m")
ym_end = pd.Period(end, freq="M").strftime("%Y-%m")
trend = data.q(
    """
    SELECT year_month, UPPER(stock_location_type) AS loc_type,
           SUM(closing_units) AS units, SUM(closing_stock_value) AS value_egp
    FROM views.stock_monthly
    WHERE year_month BETWEEN ? AND ?
    GROUP BY year_month, UPPER(stock_location_type)
    ORDER BY year_month
    """,
    (ym_start, ym_end),
)
val_fig = go.Figure()
for loc_type, color in zip(("BRANCH", "WAREHOUSE"), (theme.ACCENT, theme.ACCENT_2), strict=False):
    sub = trend[trend.loc_type == loc_type]
    if sub.empty:
        continue
    val_fig.add_trace(go.Scatter(
        x=pd.to_datetime(sub.year_month + "-01"), y=sub.value_egp, name=loc_type.title(),
        stackgroup="value", line={"width": 1.5, "color": color},
        hovertemplate="%{x|%b %Y}: EGP %{y:,.0f}<extra></extra>",
    ))
val_fig.update_layout(title="Closing stock value by location type")
theme.apply_plotly_style(val_fig)
val_fig.update_xaxes(tickformat="%b %Y")

u_fig = go.Figure()
for loc_type, color in zip(("BRANCH", "WAREHOUSE"), (theme.ACCENT, theme.ACCENT_2), strict=False):
    sub = trend[trend.loc_type == loc_type]
    if sub.empty:
        continue
    u_fig.add_trace(go.Scatter(
        x=pd.to_datetime(sub.year_month + "-01"), y=sub.units, name=loc_type.title(),
        stackgroup="units", line={"width": 1.5, "color": color},
        hovertemplate="%{x|%b %Y}: %{y:,.0f} units<extra></extra>",
    ))
u_fig.update_layout(title="Closing stock units by location type")
theme.apply_plotly_style(u_fig)
u_fig.update_xaxes(tickformat="%b %Y")

t_col, u_col = st.columns(2)
with t_col:
    st.plotly_chart(val_fig, width="stretch", config={"displayModeBar": False})
with u_col:
    st.plotly_chart(u_fig, width="stretch", config={"displayModeBar": False})

# ------------------------------------------- category mix & status (T072) --
cat_mix = data.q(
    """
    SELECT product_category AS category, SUM(closing_stock_value) AS value_egp,
           SUM(closing_units) AS units
    FROM views.stock_latest GROUP BY 1 ORDER BY 2 DESC
    """
)
if len(cat_mix) > 8:
    head8, tail = cat_mix.iloc[:8].copy(), cat_mix.iloc[8:].copy()
    head8.loc[len(head8)] = ["Other", tail.value_egp.sum(), tail.units.sum()]
    cat_plot = head8
else:
    cat_plot = cat_mix

status = data.q(
    """
    SELECT stock_status AS status, COUNT(*) AS cells,
           SUM(closing_stock_value) AS value_egp
    FROM views.stock_latest GROUP BY 1 ORDER BY 2 DESC
    """
)

cat_fig = go.Figure(go.Pie(
    hole=0.56, labels=cat_plot.category, values=cat_plot.value_egp,
    marker={"colors": theme.COLORS}, textinfo="percent",
    customdata=cat_plot.units,
    hovertemplate="%{label}: EGP %{value:,.0f} (%{percent}) \u00b7 %{customdata:,.0f} units<extra></extra>",
))
cat_fig.update_layout(title=f"Stock value mix by category — {latest_month}")
theme.apply_plotly_style(cat_fig)

status_fig = go.Figure(go.Pie(
    hole=0.56, labels=status.status, values=status.value_egp,
    marker={"colors": [theme.WARN, theme.ACCENT_2, theme.ACCENT], "line": {"color": theme.CARD, "width": 2}},
    textinfo="label+percent",
    customdata=status.cells,
    hovertemplate="%{label}: EGP %{value:,.0f} (%{percent}) \u00b7 %{customdata:,} cells<extra></extra>",
))
status_fig.update_layout(title=f"Stock status buckets — {latest_month}")
theme.apply_plotly_style(status_fig)

m_col, s_col = st.columns(2)
with m_col:
    st.plotly_chart(cat_fig, width="stretch", config={"displayModeBar": False})
with s_col:
    st.plotly_chart(status_fig, width="stretch", config={"displayModeBar": False})

# ------------------------------------------------- risk alerts table (T073) --
alerts = data.q(
    """
    SELECT location_label AS location, stock_location_type AS type,
           location_governorate_ar AS governorate, product_category AS category,
           closing_units AS units, closing_stock_value AS value_egp,
           stockout_risk_score AS risk
    FROM views.stock_latest
    ORDER BY risk DESC LIMIT 10
    """
)


def _risk_style(v: float) -> str:
    if v >= 0.70:
        return f"color: {theme.BAD}; font-weight: 600;"
    if v >= 0.60:
        return f"color: {theme.WARN}; font-weight: 600;"
    return f"color: {theme.TEXT_MUTED};"


theme.section_header(f"Top-10 stockout-risk alerts — {latest_month}")
st.dataframe(
    alerts.style.map(_risk_style, subset=["risk"]),
    hide_index=True,
    column_config={
        "location": st.column_config.TextColumn("Location"),
        "type": st.column_config.TextColumn("Type", width="small"),
        "governorate": st.column_config.TextColumn("Governorate", width="small"),
        "category": st.column_config.TextColumn("Category"),
        "units": st.column_config.NumberColumn("Units", format="%.0f"),
        "value_egp": st.column_config.NumberColumn("Value (EGP)", format="%.0f"),
        "risk": st.column_config.NumberColumn("Stockout risk", format="%.2f"),
    },
)

# -------------------------------------------------------- notes (T074) --
with st.expander("Data notes - definitions & caveats for this page", expanded=False):
    st.markdown(
        f"""
- **Grain**: `monthly_stock` is month × location × category ({int(snap.cells)} cells in the
  latest snapshot across {int(snap.locations)} locations = 80 branches + 12 warehouses).
  Stock is tracked per **category**, not per SKU.
- **Two thresholds, both from real policy**: the "% locations at risk" KPI counts cells
  with `stockout_risk_score \u2265 0.70` (deck alert line, task definition); the 'Low stock'
  bucket in `views.stock_status` triggers at \u2265 0.60. Both are labeled wherever used.
- **Status buckets** (view policy): risk \u2265 0.60 \u2192 Low stock; else top-decile closing
  units within (month, category) \u2192 Overstock; else In stock.
- **A7 scale**: closing stock value (~{theme.fmt_egp(float(snap.value_egp))}) sits above
  yearly net sales — a stock-holding retailer's normal profile; no adjustment applied.
  Use stock analytics as absolute levels, never as a revenue ratio.
- **Trend** follows the sidebar period (month-level, so the boundary month is full).
  Snapshot KPIs always use `{latest_month}` regardless of the selector — they describe
  the dataset's last state, not the selected window.
- **Data through {DATA_END.isoformat()}**.
"""
    )
