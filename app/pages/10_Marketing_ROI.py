"""Marketing ROI & Campaign Performance (S15).

Scope matrix S15: spend, impressions and clicks are real. Attribution is rebuilt
under audit A2 from real orders in each campaign's window and governorate, so it
is directional and non-additive across campaigns - never causal ROAS.
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

channels = data.q(
    "SELECT DISTINCT channel FROM views.campaigns_clean ORDER BY 1"
).iloc[:, 0].tolist()
channel = st.sidebar.selectbox("Campaign channel", ["All channels", *channels])
channel_sql = "" if channel == "All channels" else " AND channel = ?"


def _params(window: tuple, *, channel_filter: bool = True) -> tuple:
    params: tuple = tuple(window)
    if channel_filter and channel != "All channels":
        params += (channel,)
    return params


def _prior(prior: dict | None, key: str):
    return None if prior is None else prior[key]


def _card(col, title: str, value: str, delta: tuple, sub: str, tone: str | None = None) -> None:
    text, up, good = delta
    with col:
        theme.kpi_card(title, value, delta=text, delta_up=up, delta_good=good, sub=sub, tone=tone)


# ------------------------------------------------------------- campaign KPIs --
def _campaign_kpis(window: tuple) -> dict:
    row = data.q(
        """
        SELECT COUNT(*) AS campaigns,
               SUM(spend_EGP) AS spend,
               SUM(attributed_net_real) AS net,
               SUM(attributed_orders_real) AS orders,
               SUM(impressions) AS impressions,
               SUM(clicks) AS clicks,
               SUM(budget_EGP) AS budget
        FROM views.campaigns_clean
        WHERE start_date BETWEEN ? AND ?
        """
        + channel_sql,
        _params(window),
    ).iloc[0]
    spend = float(row.spend) if pd.notna(row.spend) else 0.0
    net = float(row.net) if pd.notna(row.net) else 0.0
    orders = int(row.orders or 0)
    impressions = int(row.impressions or 0)
    clicks = int(row.clicks or 0)
    budget = float(row.budget) if pd.notna(row.budget) else 0.0
    return {
        "campaigns": int(row.campaigns or 0),
        "spend": spend,
        "net": net,
        "orders": orders,
        "impressions": impressions,
        "clicks": clicks,
        "budget": budget,
        "roas": net / spend if spend else 0.0,
        "ctr": clicks / impressions if impressions else 0.0,
        "cpa": spend / orders if orders else 0.0,
        "budget_utilization": spend / budget if budget else 0.0,
    }


cur = _campaign_kpis((start, end))
pri = _campaign_kpis(prev_window) if prev_window else None

theme.page_header(
    "Marketing ROI & Campaign Performance",
    f"Reporting period: **{label}** · {cur['campaigns']:,} campaigns launched · "
    f"attribution rebuilt from real orders (A2) · data through {DATA_END.isoformat()}",
    eyebrow="Growth",
    badges=(('Directional attribution', 'warn'),),
)

cards = st.columns(4)
_card(
    cards[0], "Campaign spend", theme.fmt_egp(cur["spend"]),
    _delta(cur["spend"], _prior(pri, "spend")),
    f"{cur['campaigns']:,} campaigns · {cur['budget_utilization']:.1%} of budget", "amber",
)
_card(
    cards[1], "Attributed net", theme.fmt_egp(cur["net"]),
    _delta(cur["net"], _prior(pri, "net")),
    "A2: real orders in window × governorate", "blue",
)
_card(
    cards[2], "ROAS", f"{cur['roas']:.2f}x",
    _delta(cur["roas"], _prior(pri, "roas")),
    f"CPA EGP {cur['cpa']:,.0f} · directional, not causal", "green",
)
_card(
    cards[3], "CTR", theme.fmt_pct(cur["ctr"]),
    _delta(cur["ctr"], _prior(pri, "ctr")),
    f"{cur['clicks']:,} clicks / {cur['impressions']:,} impressions", "teal",
)

# Insights-first strip (App Shell v3): from the KPI dicts above.
theme.insight_strip([
    {
        "icon": "\U0001F4B0", "label": "ROAS",
        "value": f"{cur['roas']:.2f}x",
        "sub": "attributed net / spend · directional, not causal (A2)",
        "tone": "good" if pri is None or cur["roas"] >= pri["roas"] else "warn",
    },
    {
        "icon": "\U0001F3AF", "label": "Budget utilization",
        "value": f"{cur['budget_utilization']:.1%}",
        "sub": f"{cur['campaigns']:,} campaigns launched in the window",
        "tone": "neutral",
    },
    {
        "icon": "\U0001F5B1\uFE0F", "label": "CTR",
        "value": theme.fmt_pct(cur["ctr"]),
        "sub": f"{cur['clicks']:,} clicks / {cur['impressions']:,} impressions",
        "tone": "good" if pri is None or cur["ctr"] >= pri["ctr"] else "warn",
    },
])

st.divider()

# ---------------------------------------------------------------- trends ----
trend = data.q(
    """
    SELECT strftime(start_date, '%Y-%m') AS ym,
           COUNT(*) AS campaigns,
           SUM(spend_EGP) AS spend,
           SUM(attributed_net_real) AS net,
           SUM(attributed_orders_real) AS orders,
           SUM(impressions) AS impressions,
           SUM(clicks) AS clicks
    FROM views.campaigns_clean
    WHERE start_date BETWEEN ? AND ?
    """
    + channel_sql
    + " GROUP BY 1 ORDER BY 1",
    _params((start, end)),
)
trend["roas"] = trend.net / trend.spend.where(trend.spend > 0)

trend_fig = go.Figure()
trend_fig.add_trace(go.Bar(
    x=trend.ym, y=trend.spend,
    name="Spend (EGP)", marker_color=theme.ACCENT,
    customdata=trend.net,
    hovertemplate=(
        "%{x}: spend EGP %{y:,.0f}<br>Attributed net EGP %{customdata:,.0f}<extra></extra>"
    ),
))
trend_fig.add_trace(go.Scatter(
    x=trend.ym, y=trend.roas,
    name="ROAS", mode="lines+markers", yaxis="y2",
    line={"color": theme.ACCENT_2, "width": 2},
    hovertemplate="%{x}: %{y:.2f}x<extra></extra>",
))
trend_fig.update_layout(
    title="Monthly campaign spend and ROAS",
    yaxis={"title": "Spend (EGP)"},
    yaxis2={
        "title": "ROAS (attributed net / spend)", "overlaying": "y", "side": "right",
        "dtick": 2, "showgrid": False,
    },
)
theme.apply_plotly_style(trend_fig)
st.plotly_chart(trend_fig, width="stretch", config={"displayModeBar": False})
st.caption(
    "Campaigns are grouped by start month; spend and attributed net are full "
    "campaign totals, not prorated to the days that fall inside the window."
)

# --------------------------------------------------------- channel table ----
channel_df = data.q(
    """
    SELECT channel,
           COUNT(*) AS campaigns,
           SUM(spend_EGP) AS spend,
           SUM(attributed_net_real) AS net,
           SUM(attributed_orders_real) AS orders,
           SUM(impressions) AS impressions,
           SUM(clicks) AS clicks,
           SUM(budget_EGP) AS budget
    FROM views.campaigns_clean
    WHERE start_date BETWEEN ? AND ?
    GROUP BY 1 ORDER BY net DESC
    """,
    (start, end),
)
channel_df["roas"] = channel_df.net / channel_df.spend.where(channel_df.spend > 0)
channel_df["ctr"] = channel_df.clicks / channel_df.impressions.where(channel_df.impressions > 0)
channel_df["cpa"] = channel_df.spend / channel_df.orders.where(channel_df.orders > 0)
channel_df["budget_utilization"] = channel_df.spend / channel_df.budget.where(channel_df.budget > 0)

channel_fig = go.Figure(go.Bar(
    x=channel_df.roas, y=channel_df.channel, orientation="h",
    marker_color=theme.ACCENT,
    text=[f"{roas:.2f}x · {theme.fmt_egp(spend)}"
          for roas, spend in zip(channel_df.roas, channel_df.spend, strict=True)],
    textposition="outside", cliponaxis=False,
    customdata=channel_df[["net", "orders", "ctr", "cpa"]].to_numpy(),
    hovertemplate=(
        "%{y}<br>ROAS %{x:.2f}x<br>Attributed net EGP %{customdata[0]:,.0f}"
        "<br>Attributed orders %{customdata[1]:,.0f}<br>CTR %{customdata[2]:.2%}"
        "<br>CPA EGP %{customdata[3]:,.0f}<extra></extra>"
    ),
))
channel_fig.update_layout(title="Channel comparison - ROAS")
theme.apply_plotly_style(channel_fig)
channel_fig.update_yaxes(autorange="reversed")
channel_fig.update_xaxes(range=[0, float(channel_df.roas.max()) * 1.32])

budget_df = data.q(
    """
    WITH b AS (
        SELECT CASE
                   WHEN budget_utilization < 0.50 THEN 1
                   WHEN budget_utilization < 0.75 THEN 2
                   WHEN budget_utilization < 0.90 THEN 3
                   WHEN budget_utilization <= 1.00 THEN 4
                   ELSE 5
               END AS bucket_order,
               CASE
                   WHEN budget_utilization < 0.50 THEN '<50%'
                   WHEN budget_utilization < 0.75 THEN '50-75%'
                   WHEN budget_utilization < 0.90 THEN '75-90%'
                   WHEN budget_utilization <= 1.00 THEN '90-100%'
                   ELSE '>100%'
               END AS bucket,
               spend_EGP,
               budget_EGP
        FROM views.campaigns_clean
        WHERE start_date BETWEEN ? AND ?
        """
    + channel_sql
    + """
    )
    SELECT bucket, COUNT(*) AS campaigns, SUM(spend_EGP) AS spend, SUM(budget_EGP) AS budget
    FROM b GROUP BY bucket, bucket_order ORDER BY bucket_order
    """,
    _params((start, end)),
)

budget_fig = go.Figure(go.Bar(
    x=budget_df.bucket, y=budget_df.campaigns,
    marker_color=theme.ACCENT_2,
    customdata=budget_df[["spend", "budget"]].to_numpy(),
    text=budget_df.campaigns,
    textposition="outside", cliponaxis=False,
    hovertemplate=(
        "%{x}<br>%{y:,} campaigns<br>Spend EGP %{customdata[0]:,.0f}"
        "<br>Budget EGP %{customdata[1]:,.0f}<extra></extra>"
    ),
))
budget_fig.update_layout(
    title="Budget utilization distribution",
    yaxis={"title": "Campaigns"},
)
theme.apply_plotly_style(budget_fig)

chart_l, chart_r = st.columns(2)
with chart_l:
    st.plotly_chart(channel_fig, width="stretch", config={"displayModeBar": False})
with chart_r:
    st.plotly_chart(budget_fig, width="stretch", config={"displayModeBar": False})
st.caption(
    "Channel comparison labels show ROAS · spend and always use all channels "
    "regardless of the sidebar filter. Budget utilization = spend / campaign "
    "budget as recorded."
)

# ---------------------------------------------------------- campaign table --
st.subheader("Top campaigns by attributed net")
campaigns = data.q(
    """
    SELECT campaign_id, channel, target_audience, governorate_ar,
           start_date, end_date, budget_EGP, spend_EGP,
           attributed_orders_real, attributed_net_real,
           ctr, budget_utilization
    FROM views.campaigns_clean
    WHERE start_date BETWEEN ? AND ?
    """
    + channel_sql
    + " ORDER BY attributed_net_real DESC LIMIT 20",
    _params((start, end)),
)
campaigns["roas"] = campaigns.attributed_net_real / campaigns.spend_EGP.where(campaigns.spend_EGP > 0)
campaigns["cpa"] = campaigns.spend_EGP / campaigns.attributed_orders_real.where(
    campaigns.attributed_orders_real > 0
)
campaigns["ctr"] = campaigns.ctr * 100
campaigns["budget_utilization"] = campaigns.budget_utilization * 100

st.dataframe(
    campaigns,
    hide_index=True,
    column_config={
        "campaign_id": st.column_config.TextColumn("Campaign", width="small"),
        "channel": st.column_config.TextColumn("Channel", width="small"),
        "target_audience": st.column_config.TextColumn("Audience", width="small"),
        "governorate_ar": st.column_config.TextColumn("Governorate", width="small"),
        "start_date": st.column_config.DateColumn("Start"),
        "end_date": st.column_config.DateColumn("End"),
        "budget_EGP": st.column_config.NumberColumn("Budget (EGP)", format="%.0f"),
        "spend_EGP": st.column_config.NumberColumn("Spend (EGP)", format="%.0f"),
        "attributed_orders_real": st.column_config.NumberColumn("Attributed orders", format="%.0f"),
        "attributed_net_real": st.column_config.NumberColumn("Attributed net (EGP)", format="%.0f"),
        "ctr": st.column_config.NumberColumn("CTR (%)", format="%.2f"),
        "budget_utilization": st.column_config.NumberColumn("Budget use (%)", format="%.1f"),
        "roas": st.column_config.NumberColumn("ROAS", format="%.2fx"),
        "cpa": st.column_config.NumberColumn("CPA (EGP)", format="%.0f"),
    },
)
st.caption(
    "Top 20 campaigns launched in the window, sorted by attributed net. "
    "The table is campaign-level; overlapping campaigns can attribute the same orders. "
    "Low-spend campaigns can show extreme ROAS because attribution is campaign-window "
    "based - read spend and attributed orders together."
)

with st.expander("Data notes - definitions & caveats for this page", expanded=False):
    st.markdown(
        f"""
- **Grain**: `views.campaigns_clean` is one row per campaign (2,200 campaigns,
  2018-10 → {DATA_END.isoformat()}). Spend, budget, impressions and clicks are
  source fields; CTR = clicks / impressions.
- **Audit A2 - rebuilt attribution**: `attributed_orders_real` and
  `attributed_net_real` are **reconstructed** from real orders whose order date
  falls inside the campaign window and whose customer governorate matches the
  campaign governorate. Guest orders are excluded because they carry no
  governorate. The source `orders_attributed` column (24.1M) is never used.
- **Attribution is directional and non-additive**: overlapping campaigns in the
  same governorate can each claim the same orders. Do not sum attributed net
  across campaigns or treat it as incremental revenue.
- **ROAS** = attributed net / spend. **CPA** = spend / attributed orders. Neither
  is causal: there is no holdout, control group, conversion funnel, or incrementality
  test in the dataset.
- **Period rule**: campaigns are counted when `start_date` falls in the window, and
  spend/results are full campaign totals - not prorated. A campaign that starts on
  the last day of the window contributes its entire spend.
- **Budget utilization** = spend / budget. Values above 100% mean recorded spend
  exceeded the recorded budget; they are left visible, not clipped.
- **Channel filter** applies to KPIs, the trend, budget buckets and the campaign
  table. The channel comparison chart always shows all channels.
- **No campaign names**: the source has no campaign-name field, only IDs.
"""
    )
