"""Supply Chain & Logistics (S8) - outbound delivery + transfer pipeline.

Scope matrix S8: shipments and transfers are real; there is no live tracking,
no supplier-to-shipment link, and transfer status is a snapshot label.
Destination governorate on a shipment is the customer address, not the branch.
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
    selected_period,
    window_label,
)

start, end, label, mode = selected_period()
prev_window = previous_period(start, end, mode)
prev_label = window_label(prev_window, empty="no comparison window")
_delta = partial(delta_label, label=prev_label)

carriers = data.q("SELECT DISTINCT carrier FROM views.delivery_ops ORDER BY 1").iloc[:, 0].tolist()
carrier = st.sidebar.selectbox("Carrier", ["All carriers", *carriers])
carrier_sql = "" if carrier == "All carriers" else " AND carrier = ?"


def _params(window: tuple, *, carrier_filter: bool = True) -> tuple:
    params: tuple = tuple(window)
    if carrier_filter and carrier != "All carriers":
        params += (carrier,)
    return params


def _prior(prior: dict | None, key: str):
    return None if prior is None else prior[key]


def _card(col, title: str, value: str, delta: tuple, sub: str, tone: str | None = None) -> None:
    text, up, good = delta
    with col:
        theme.kpi_card(title, value, delta=text, delta_up=up, delta_good=good, sub=sub, tone=tone)


# ------------------------------------------------------------ delivery KPIs --
def _delivery_kpis(window: tuple) -> dict:
    row = data.q(
        """
        SELECT COUNT(*) AS shipments,
               COUNT(*) FILTER (WHERE is_delayed = 1) AS delayed,
               AVG(delivery_days) AS avg_days,
               SUM(shipping_fee_EGP) AS fee
        FROM views.delivery_ops
        WHERE ship_date BETWEEN ? AND ?
        """
        + carrier_sql,
        _params(window),
    ).iloc[0]
    shipments = int(row.shipments or 0)
    delayed = int(row.delayed or 0)
    return {
        "shipments": shipments,
        "delayed": delayed,
        "delayed_rate": delayed / shipments if shipments else 0.0,
        "avg_days": float(row.avg_days) if pd.notna(row.avg_days) else 0.0,
        "fee": float(row.fee) if pd.notna(row.fee) else 0.0,
    }


def _transfer_kpis(window: tuple) -> dict:
    row = data.q(
        """
        SELECT COUNT(*) AS transfers,
               COUNT(*) FILTER (WHERE transfer_status = 'In transit') AS in_transit,
               COUNT(*) FILTER (WHERE transfer_status = 'Partially received') AS partial,
               SUM(units) AS units,
               SUM(transport_cost_EGP) AS cost
        FROM views.transfer_ops
        WHERE transfer_date BETWEEN ? AND ?
        """,
        window,
    ).iloc[0]
    transfers = int(row.transfers or 0)
    units = int(row.units or 0)
    cost = float(row.cost or 0.0)
    return {
        "transfers": transfers,
        "in_transit": int(row.in_transit or 0),
        "partial": int(row.partial or 0),
        "open": int(row.in_transit or 0) + int(row.partial or 0),
        "units": units,
        "cost": cost,
        "cost_per_unit": cost / units if units else 0.0,
    }


cur_d = _delivery_kpis((start, end))
pri_d = _delivery_kpis(prev_window) if prev_window else None
cur_t = _transfer_kpis((start, end))
pri_t = _transfer_kpis(prev_window) if prev_window else None

theme.page_header(
    "Supply Chain & Logistics",
    f"Reporting period: **{label}** · {cur_d['shipments']:,} outbound shipments · "
    f"{cur_t['transfers']:,} inventory transfers · data through {DATA_END.isoformat()}",
    eyebrow="Operations",
    badges=('Outbound + transfers',),
)

cards = st.columns(4)
_card(
    cards[0], "Shipments", theme.fmt_int(cur_d["shipments"]),
    _delta(cur_d["shipments"], _prior(pri_d, "shipments")),
    "E-commerce orders in period", "teal",
)
_card(
    cards[1], "Delayed rate", theme.fmt_pct(cur_d["delayed_rate"]),
    _delta(cur_d["delayed_rate"], _prior(pri_d, "delayed_rate"), lower_is_better=True),
    f"{cur_d['delayed']:,} delayed shipments", "red",
)
_card(
    cards[2], "Avg delivery days", f"{cur_d['avg_days']:.1f}",
    _delta(cur_d["avg_days"], _prior(pri_d, "avg_days"), lower_is_better=True),
    "ship date to delivery date", "amber",
)
_card(
    cards[3], "Shipping fees", theme.fmt_egp(cur_d["fee"]),
    _delta(cur_d["fee"], _prior(pri_d, "fee")),
    "charged to customers; no carrier cost data", "violet",
)

# Insights-first strip (App Shell v3): from the KPI dicts above.
theme.insight_strip([
    {
        "icon": "\u23F1\uFE0F", "label": "Delayed rate",
        "value": theme.fmt_pct(cur_d["delayed_rate"]),
        "sub": f"{cur_d['delayed']:,} of {cur_d['shipments']:,} shipments delayed",
        "tone": "good" if pri_d is None or cur_d["delayed_rate"] <= pri_d["delayed_rate"] else "bad",
    },
    {
        "icon": "\U0001F69A", "label": "Avg delivery time",
        "value": f"{cur_d['avg_days']:.1f} days",
        "sub": "ship date to delivery date",
        "tone": "good" if pri_d is None or cur_d["avg_days"] <= pri_d["avg_days"] else "warn",
    },
    {
        "icon": "\U0001F4E6", "label": "Open transfers",
        "value": f"{cur_t['open']:,}",
        "sub": f"{cur_t['in_transit']:,} in transit · {cur_t['partial']:,} partially received",
        "tone": "warn" if cur_t["open"] else "good",
    },
])

st.divider()

# ------------------------------------------------------- outbound delivery --
st.subheader("Outbound delivery")
st.caption(
    f"Carrier filter: **{carrier}** · status values in the source are only "
    "Delivered / Delayed (no live tracking)."
)

delivery_trend = data.q(
    """
    SELECT ym,
           COUNT(*) AS shipments,
           COUNT(*) FILTER (WHERE is_delayed = 1) AS delayed,
           AVG(delivery_days) AS avg_days
    FROM views.delivery_ops
    WHERE ship_date BETWEEN ? AND ?
    """
    + carrier_sql
    + " GROUP BY 1 ORDER BY 1",
    _params((start, end)),
)
delivery_trend["delayed_rate"] = (
    delivery_trend.delayed / delivery_trend.shipments.where(delivery_trend.shipments > 0)
)

trend_fig = go.Figure()
trend_fig.add_trace(go.Bar(
    x=delivery_trend.ym, y=delivery_trend.shipments,
    name="Shipments", marker_color=theme.ACCENT,
    hovertemplate="%{x}: %{y:,} shipments<extra></extra>",
))
trend_fig.add_trace(go.Scatter(
    x=delivery_trend.ym, y=delivery_trend.delayed_rate,
    name="Delayed rate", mode="lines+markers", yaxis="y2",
    line={"color": theme.BAD, "width": 2},
    hovertemplate="%{x}: %{y:.1%} delayed<extra></extra>",
))
trend_fig.update_layout(
    title="Monthly shipments and delayed rate",
    yaxis={"title": "Shipments"},
    yaxis2={
        "title": "Delayed rate", "overlaying": "y", "side": "right",
        "tickformat": ".1%", "showgrid": False,
    },
)
theme.apply_plotly_style(trend_fig)

carrier_df = data.q(
    """
    SELECT carrier,
           COUNT(*) AS shipments,
           COUNT(*) FILTER (WHERE is_delayed = 1) AS delayed,
           AVG(delivery_days) AS avg_days,
           AVG(shipping_fee_EGP) AS avg_fee
    FROM views.delivery_ops
    WHERE ship_date BETWEEN ? AND ?
    GROUP BY 1 ORDER BY shipments DESC
    """,
    (start, end),
)
carrier_df["delayed_rate"] = carrier_df.delayed / carrier_df.shipments
carrier_df = carrier_df.sort_values("delayed_rate", ascending=True)

carrier_fig = go.Figure(go.Bar(
    x=carrier_df.delayed_rate, y=carrier_df.carrier, orientation="h",
    marker_color=theme.ACCENT_2,
    text=[f"{rate:.1%} · {n:,}"
          for rate, n in zip(carrier_df.delayed_rate, carrier_df.shipments, strict=True)],
    textposition="outside", cliponaxis=False,
    customdata=carrier_df[["shipments", "avg_days", "avg_fee"]].to_numpy(),
    hovertemplate=(
        "%{y}<br>Delayed rate %{x:.1%}<br>Shipments %{customdata[0]:,}"
        "<br>Avg delivery days %{customdata[1]:.2f}"
        "<br>Avg fee EGP %{customdata[2]:,.1f}<extra></extra>"
    ),
))
carrier_fig.update_layout(title="Carrier comparison - delayed rate")
theme.apply_plotly_style(carrier_fig)
carrier_fig.update_xaxes(tickformat=".1%")
carrier_fig.update_yaxes(autorange="reversed")

chart_l, chart_r = st.columns(2)
with chart_l:
    st.plotly_chart(trend_fig, width="stretch", config={"displayModeBar": False})
with chart_r:
    st.plotly_chart(carrier_fig, width="stretch", config={"displayModeBar": False})
    st.caption("Labels: delayed rate · shipment count.")

dest = data.q(
    """
    SELECT destination_governorate AS governorate,
           COUNT(*) AS shipments,
           COUNT(*) FILTER (WHERE is_delayed = 1) AS delayed,
           AVG(delivery_days) AS avg_days,
           SUM(shipping_fee_EGP) AS fee
    FROM views.delivery_ops
    WHERE ship_date BETWEEN ? AND ?
    """
    + carrier_sql
    + " GROUP BY 1 ORDER BY shipments DESC",
    _params((start, end)),
)
dest["delayed_rate"] = dest.delayed / dest.shipments
dest_top = dest.head(12).sort_values("delayed_rate")

dest_fig = go.Figure(go.Bar(
    x=dest_top.delayed_rate, y=dest_top.governorate, orientation="h",
    marker_color=[theme.BAD if rate >= cur_d["delayed_rate"] else theme.GOOD
                  for rate in dest_top.delayed_rate],
    text=[f"{rate:.1%} · {n:,}" for rate, n in
          zip(dest_top.delayed_rate, dest_top.shipments, strict=True)],
    textposition="outside", cliponaxis=False,
    customdata=dest_top[["shipments", "avg_days", "fee"]].to_numpy(),
    hovertemplate=(
        "%{y}<br>Delayed rate %{x:.1%}<br>Shipments %{customdata[0]:,}"
        "<br>Avg delivery days %{customdata[1]:.2f}"
        "<br>Shipping fees EGP %{customdata[2]:,.0f}<extra></extra>"
    ),
))
dest_fig.update_layout(
    title="Top 12 destination governorates - delayed rate",
    height=420,
)
theme.apply_plotly_style(dest_fig)
dest_fig.update_xaxes(tickformat=".1%")
dest_fig.update_yaxes(autorange="reversed")
st.plotly_chart(dest_fig, width="stretch", config={"displayModeBar": False})
st.caption(
    f"Top 12 of {len(dest)} destination governorates by shipment count. "
    "Bars red = at or above the filtered delayed rate; green = below it."
)

st.divider()

# -------------------------------------------------------- transfer pipeline --
st.subheader("Inventory transfer pipeline")
st.caption(
    "Transfers move stock from warehouses to branches. Cost is recorded once per "
    "transfer, and units are the sum of transfer lines."
)

t_cards = st.columns(4)
with t_cards[0]:
    theme.kpi_card(
        "Transfers", theme.fmt_int(cur_t["transfers"]),
        sub=f"vs {theme.fmt_int(pri_t['transfers']) if pri_t else 'n/a'} in prior window",
        tone="teal",
    )
with t_cards[1]:
    theme.kpi_card(
        "Units moved", theme.fmt_int(cur_t["units"]),
        sub=f"{cur_t['units'] / max(cur_t['transfers'], 1):,.0f} units per transfer",
        tone="blue",
    )
with t_cards[2]:
    theme.kpi_card(
        "Transport cost", theme.fmt_egp(cur_t["cost"]),
        sub=f"EGP {cur_t['cost_per_unit']:,.2f} per unit moved",
        tone="amber",
    )
with t_cards[3]:
    theme.kpi_card(
        "Open transfers", theme.fmt_int(cur_t["open"]),
        sub=f"{cur_t['in_transit']:,} in transit · {cur_t['partial']:,} partially received",
        tone="violet",
    )

transfer_trend = data.q(
    """
    SELECT ym,
           COUNT(*) AS transfers,
           COUNT(*) FILTER (WHERE transfer_status = 'In transit') AS in_transit,
           COUNT(*) FILTER (WHERE transfer_status = 'Partially received') AS partial,
           COUNT(*) FILTER (WHERE transfer_status <> 'Completed') AS open_transfers,
           SUM(transport_cost_EGP) AS cost,
           SUM(units) AS units
    FROM views.transfer_ops
    WHERE transfer_date BETWEEN ? AND ?
    GROUP BY 1 ORDER BY 1
    """,
    (start, end),
)

transfer_fig = go.Figure()
transfer_fig.add_trace(go.Bar(
    x=transfer_trend.ym, y=transfer_trend.cost,
    name="Transport cost (EGP)", marker_color=theme.ACCENT_2,
    hovertemplate="%{x}: EGP %{y:,.0f}<extra></extra>",
))
transfer_fig.add_trace(go.Scatter(
    x=transfer_trend.ym, y=transfer_trend.open_transfers,
    name="Open transfers", mode="lines+markers", yaxis="y2",
    line={"color": theme.WARN, "width": 2},
    hovertemplate="%{x}: %{y:,} open<extra></extra>",
))
transfer_fig.update_layout(
    title="Monthly transfer cost and open transfers",
    yaxis={"title": "Transport cost (EGP)"},
    yaxis2={
        "title": "Open transfers", "overlaying": "y", "side": "right",
        "showgrid": False,
    },
)
theme.apply_plotly_style(transfer_fig)

status_df = data.q(
    """
    SELECT transfer_status,
           COUNT(*) AS transfers,
           SUM(transport_cost_EGP) AS cost
    FROM views.transfer_ops
    WHERE transfer_date BETWEEN ? AND ?
    GROUP BY 1 ORDER BY transfers DESC
    """,
    (start, end),
)

status_fig = go.Figure(go.Pie(
    labels=status_df.transfer_status,
    values=status_df.transfers,
    hole=0.55,
    marker={"colors": [theme.GOOD, theme.WARN, theme.ACCENT]},
    textinfo="percent",
    hovertemplate="%{label}: %{value:,} transfers<br>EGP %{customdata:,.0f}<extra></extra>",
    customdata=status_df.cost,
))
status_fig.update_layout(title="Transfer status mix")
theme.apply_plotly_style(status_fig)

t_chart_l, t_chart_r = st.columns(2)
with t_chart_l:
    st.plotly_chart(transfer_fig, width="stretch", config={"displayModeBar": False})
with t_chart_r:
    st.plotly_chart(status_fig, width="stretch", config={"displayModeBar": False})

dest_table = data.q(
    """
    SELECT destination_governorate AS governorate,
           COUNT(*) AS transfers,
           SUM(units) AS units,
           SUM(transport_cost_EGP) AS transport_cost,
           SUM(transport_cost_EGP) / NULLIF(SUM(units), 0) AS cost_per_unit,
           COUNT(*) FILTER (WHERE transfer_status <> 'Completed') AS open_transfers
    FROM views.transfer_ops
    WHERE transfer_date BETWEEN ? AND ?
    GROUP BY 1 ORDER BY transport_cost DESC
    """,
    (start, end),
)
st.markdown("##### Transfer destinations in the window")
st.dataframe(
    dest_table,
    hide_index=True,
    column_config={
        "governorate": st.column_config.TextColumn("Destination governorate"),
        "transfers": st.column_config.NumberColumn("Transfers", format="%.0f"),
        "units": st.column_config.NumberColumn("Units", format="%.0f"),
        "transport_cost": st.column_config.NumberColumn("Transport cost (EGP)", format="%.0f"),
        "cost_per_unit": st.column_config.NumberColumn("EGP / unit", format="%.2f"),
        "open_transfers": st.column_config.NumberColumn("Open", format="%.0f"),
    },
)
st.caption(
    "Destination branch governorate, sorted by transport cost. "
    "Open = In transit + Partially received."
)

with st.expander("Data notes - definitions & caveats for this page", expanded=False):
    st.markdown(
        f"""
- **Delivery grain**: one row per shipment in `views.delivery_ops` (97,660 shipments,
  2018-10-19 → {DATA_END.isoformat()}). Every shipment maps 1:1 to an **E-commerce** order
  in this dataset; there are no shipments for POS or wholesale orders.
- **Status caveat**: the source only carries `Delivered` / `Delayed` snapshots. There is
  no live tracking, no in-transit queue, and no carrier SLA or promised-delivery field.
  "Delayed" is the source label, not a lateness calculation.
- **Delivery days** = `delivery_date − ship_date`, in calendar days (0–7 in this data).
- **Destination geography** = `ship_to_governorate`, the **customer address**. It is not
  the fulfilling branch's governorate (the two differ on most shipments).
- **Shipping fees** are amounts charged to customers. The dataset has no carrier cost,
  fuel surcharge, or cost-to-serve field, so fees are not a margin.
- **Transfer grain**: one row per transfer in `views.transfer_ops`; item lines are
  aggregated to units/SKUs/lines so `transport_cost_EGP` is counted once. Open transfers
  = `In transit` + `Partially received`; the source has no expected-arrival date.
- **No supplier link**: the data cannot connect a supplier PO to an outbound shipment
  or a transfer. This page therefore shows two separate operational streams.
- **Carrier filter**: applies to the delivery KPIs, trend and destination chart. The
  carrier comparison always shows all carriers so they can be compared side by side.
"""
    )
