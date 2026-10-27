"""Procurement & Supplier Analytics (S9).

Scope matrix S9: volumes, lead times and on-time rates are real; PO value is
absolute-only under audit A1 and must never be compared with COGS or revenue.
There is no contractual promised-delivery date, so on-time uses payment terms.
"""

from __future__ import annotations

import sys
from functools import partial
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import data, theme
from app.filters import (
    DATA_END,
    delta_label,
    previous_period,
    render_period_selector,
    window_label,
)

st.set_page_config(
    page_title="Procurement & Suppliers · Cottonil",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.apply_theme()

start, end, label, mode = render_period_selector()
prev_window = previous_period(start, end, mode)
prev_label = window_label(prev_window, empty="no comparison window")
_delta = partial(delta_label, label=prev_label)

materials = data.q(
    "SELECT DISTINCT material_type FROM views.procurement_monthly ORDER BY 1"
).iloc[:, 0].tolist()
material = st.sidebar.selectbox("Material type", ["All materials", *materials])
material_sql = "" if material == "All materials" else " AND material_type = ?"


def _params(window: tuple, *, material_filter: bool = True) -> tuple:
    params: tuple = (window[0].strftime("%Y-%m"), window[1].strftime("%Y-%m"))
    if material_filter and material != "All materials":
        params += (material,)
    return params


def _prior(prior: dict | None, key: str):
    return None if prior is None else prior[key]


def _card(col, title: str, value: str, delta: tuple, sub: str) -> None:
    text, up, good = delta
    with col:
        theme.kpi_card(title, value, delta=text, delta_up=up, delta_good=good, sub=sub)


# ----------------------------------------------------------- procurement KPIs --
def _procurement_kpis(window: tuple) -> dict:
    row = data.q(
        """
        SELECT COUNT(DISTINCT supplier_id) AS suppliers,
               SUM(n_purchase_orders) AS pos,
               SUM(n_lines) AS lines,
               SUM(units) AS units,
               SUM(value_EGP) AS value,
               SUM(avg_lead_days * n_lines) / NULLIF(SUM(n_lines), 0) AS avg_lead_days,
               SUM(on_time_rate * n_lines) / NULLIF(SUM(n_lines), 0) AS on_time_rate,
               SUM(partial_pos) AS partial_pos
        FROM views.procurement_monthly
        WHERE ym BETWEEN ? AND ?
        """
        + material_sql,
        _params(window),
    ).iloc[0]
    return {
        "suppliers": int(row.suppliers or 0),
        "pos": int(row.pos or 0),
        "lines": int(row.lines or 0),
        "units": int(row.units or 0),
        "value": float(row.value) if pd.notna(row.value) else 0.0,
        "lead_days": float(row.avg_lead_days) if pd.notna(row.avg_lead_days) else 0.0,
        "on_time_rate": float(row.on_time_rate) if pd.notna(row.on_time_rate) else 0.0,
        "partial_pos": int(row.partial_pos or 0),
    }


cur = _procurement_kpis((start, end))
pri = _procurement_kpis(prev_window) if prev_window else None

theme.page_header(
    "Procurement & Supplier Analytics",
    f"Reporting period: **{label}** · {cur['suppliers']} suppliers · "
    f"{cur['pos']:,} purchase orders · data through {DATA_END.isoformat()}",
    eyebrow="Operations",
    badges=(('PO value absolute-only', 'warn'),),
)

cards = st.columns(4)
_card(
    cards[0], "Purchase orders", theme.fmt_int(cur["pos"]),
    _delta(cur["pos"], _prior(pri, "pos")),
    f"{cur['suppliers']} suppliers · {cur['partial_pos']:,} partial receipts",
)
_card(
    cards[1], "PO value", theme.fmt_egp(cur["value"]),
    _delta(cur["value"], _prior(pri, "value")),
    "A1: absolute-only - never compare to COGS/revenue",
)
_card(
    cards[2], "Avg lead time", f"{cur['lead_days']:.1f} days",
    _delta(cur["lead_days"], _prior(pri, "lead_days"), lower_is_better=True),
    "PO date to item delivery date",
)
_card(
    cards[3], "On-time rate", theme.fmt_pct(cur["on_time_rate"]),
    _delta(cur["on_time_rate"], _prior(pri, "on_time_rate")),
    "within payment terms; no contractual promise date",
)

st.divider()

# ---------------------------------------------------------------- trends ----
trend = data.q(
    """
    SELECT ym,
           COUNT(DISTINCT supplier_id) AS suppliers,
           SUM(n_purchase_orders) AS pos,
           SUM(units) AS units,
           SUM(value_EGP) AS value,
           SUM(avg_lead_days * n_lines) / NULLIF(SUM(n_lines), 0) AS avg_lead_days,
           SUM(on_time_rate * n_lines) / NULLIF(SUM(n_lines), 0) AS on_time_rate
    FROM views.procurement_monthly
    WHERE ym BETWEEN ? AND ?
    """
    + material_sql
    + " GROUP BY 1 ORDER BY 1",
    _params((start, end)),
)

trend_fig = go.Figure()
trend_fig.add_trace(go.Bar(
    x=trend.ym, y=trend.value,
    name="PO value (EGP, A1)", marker_color=theme.ACCENT,
    hovertemplate="%{x}: EGP %{y:,.0f}<extra></extra>",
))
trend_fig.add_trace(go.Scatter(
    x=trend.ym, y=trend.avg_lead_days,
    name="Avg lead days", mode="lines+markers", yaxis="y2",
    line={"color": theme.ACCENT_2, "width": 2},
    hovertemplate="%{x}: %{y:.1f} days<extra></extra>",
))
trend_fig.update_layout(
    title="Monthly PO value and average lead time",
    yaxis={"title": "PO value (EGP, absolute-only)"},
    yaxis2={
        "title": "Avg lead days", "overlaying": "y", "side": "right",
        "dtick": 5, "showgrid": False,
    },
)
theme.apply_plotly_style(trend_fig)
st.plotly_chart(trend_fig, width="stretch", config={"displayModeBar": False})
st.caption(
    "PO value is the sum of recorded line costs. Audit A1: the scale is not "
    "comparable to COGS or revenue, so read it as procurement volume only."
)

# --------------------------------------------------------- material mix ----
material_df = data.q(
    """
    SELECT material_type,
           COUNT(DISTINCT supplier_id) AS suppliers,
           SUM(n_purchase_orders) AS pos,
           SUM(units) AS units,
           SUM(value_EGP) AS value,
           SUM(avg_lead_days * n_lines) / NULLIF(SUM(n_lines), 0) AS avg_lead_days,
           SUM(on_time_rate * n_lines) / NULLIF(SUM(n_lines), 0) AS on_time_rate,
           SUM(partial_pos) AS partial_pos
    FROM views.procurement_monthly
    WHERE ym BETWEEN ? AND ?
    """
    + material_sql
    + " GROUP BY 1 ORDER BY value DESC",
    _params((start, end)),
)

mix_fig = go.Figure(go.Pie(
    labels=material_df.material_type,
    values=material_df.value,
    hole=0.55,
    marker={"colors": theme.COLORS},
    textinfo="percent",
    hovertemplate="%{label}: EGP %{value:,.0f}<extra></extra>",
))
mix_fig.update_layout(title="PO value share by material type (A1)")
theme.apply_plotly_style(mix_fig)

lead_df = material_df.sort_values("avg_lead_days")
lead_fig = go.Figure(go.Bar(
    x=lead_df.avg_lead_days, y=lead_df.material_type, orientation="h",
    marker_color=theme.ACCENT_2,
    text=[f"{lead:.1f}d · {rate:.1%}"
          for lead, rate in zip(lead_df.avg_lead_days, lead_df.on_time_rate, strict=True)],
    textposition="outside", cliponaxis=False,
    customdata=lead_df[["pos", "suppliers", "value"]].to_numpy(),
    hovertemplate=(
        "%{y}<br>Avg lead %{x:.1f} days<br>POs %{customdata[0]:,}"
        "<br>Suppliers %{customdata[1]:,.0f}<br>PO value EGP %{customdata[2]:,.0f}"
        "<extra></extra>"
    ),
))
lead_fig.update_layout(title="Average lead time by material type")
theme.apply_plotly_style(lead_fig)
lead_fig.update_xaxes(title="Days from PO date to delivery")

chart_l, chart_r = st.columns(2)
with chart_l:
    st.plotly_chart(mix_fig, width="stretch", config={"displayModeBar": False})
with chart_r:
    st.plotly_chart(lead_fig, width="stretch", config={"displayModeBar": False})
    st.caption("Labels: average lead days · on-time rate.")

# --------------------------------------------------------- scorecard --------
st.subheader("Supplier scorecard")
st.caption(
    "Period-weighted from `views.procurement_monthly`; lead time and on-time rate "
    "are weighted by PO lines so small months do not dominate."
)

supplier_df = data.q(
    """
    SELECT supplier_id,
           ANY_VALUE(supplier_name_ar) AS supplier,
           ANY_VALUE(material_type) AS material,
           ANY_VALUE(city_country) AS city_country,
           SUM(n_purchase_orders) AS pos,
           SUM(units) AS units,
           SUM(value_EGP) AS value,
           SUM(avg_lead_days * n_lines) / NULLIF(SUM(n_lines), 0) AS avg_lead_days,
           SUM(on_time_rate * n_lines) / NULLIF(SUM(n_lines), 0) AS on_time_rate,
           SUM(partial_pos) AS partial_pos
    FROM views.procurement_monthly
    WHERE ym BETWEEN ? AND ?
    """
    + material_sql
    + " GROUP BY supplier_id ORDER BY value DESC",
    _params((start, end)),
)
supplier_df["on_time_rate"] = supplier_df.on_time_rate * 100

st.dataframe(
    supplier_df,
    hide_index=True,
    column_config={
        "supplier_id": st.column_config.TextColumn("Supplier ID", width="small"),
        "supplier": st.column_config.TextColumn("Supplier"),
        "material": st.column_config.TextColumn("Material", width="small"),
        "city_country": st.column_config.TextColumn("City / country", width="small"),
        "pos": st.column_config.NumberColumn("POs", format="%.0f", width="small"),
        "units": st.column_config.NumberColumn("Units", format="%.0f"),
        "value": st.column_config.NumberColumn("PO value (EGP, A1)", format="%.0f"),
        "avg_lead_days": st.column_config.NumberColumn("Avg lead days", format="%.1f"),
        "on_time_rate": st.column_config.NumberColumn("On-time (%)", format="%.1f"),
        "partial_pos": st.column_config.NumberColumn("Partial POs", format="%.0f"),
    },
)
st.caption(
    f"{len(supplier_df)} suppliers in the window, sorted by PO value. "
    "On-time = delivery on or before PO date + payment terms (45-90 days)."
)

with st.expander("Data notes - definitions & caveats for this page", expanded=False):
    st.markdown(
        f"""
- **Grain**: `views.procurement_monthly` is one row per **PO month × supplier**,
  built from 41,500 POs and 103,334 PO lines (2018-10 → {DATA_END.isoformat()}).
- **Audit A1 - read this first**: PO value (`value_EGP`) is absolute-only. The
  recorded procurement scale is not comparable to COGS or revenue and must not be
  used for spend ratios, margin, or "procurement as % of sales". This page never
  divides it by revenue.
- **On-time rate**: item delivery date ≤ PO date + supplier payment terms
  (45/60/90 days). The dataset has **no contractual promised-delivery date and no
  goods-receipt timestamp**, so this is a documented proxy, not a supplier SLA.
  Weighted by PO lines in every aggregate.
- **Lead time**: calendar days from PO date to item delivery date (0–55 days here).
- **PO status**: only `Received` and `Partial receipt` exist. `Partial POs` counts
  distinct POs with the latter flag in the window.
- **No invoice matching**: there is no invoice, payment, quality-rejection, or
  supplier-claim table. The scorecard covers volume, value, lead time and on-time
  proxy only.
- **Material filter**: applies to every KPI, chart and the scorecard.
"""
    )
