"""Wholesale & Distributor Performance (S22).

Scope matrix S22: the Wholesale channel is fully real. There is no distributor
account table and no sell-out data, so B2B accounts are aggregated reseller
customers from the sales spine, and account value is sell-in only.
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
    page_title="Wholesale & Distributors · Cottonil",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.apply_theme()

start, end, label, mode = render_period_selector()
prev_window = previous_period(start, end, mode)
prev_label = window_label(prev_window, empty="no comparison window")
_delta = partial(delta_label, label=prev_label)


def _prior(prior: dict | None, key: str):
    return None if prior is None else prior[key]


def _card(col, title: str, value: str, delta: tuple, sub: str) -> None:
    text, up, good = delta
    with col:
        theme.kpi_card(title, value, delta=text, delta_up=up, delta_good=good, sub=sub)


# ------------------------------------------------------------ wholesale KPIs --
def _wholesale_kpis(window: tuple) -> dict:
    wholesale = data.q(
        """
        SELECT COUNT(DISTINCT sales_order_id) AS orders,
               COUNT(DISTINCT customer_id) AS customers,
               SUM(net_sales) AS net,
               SUM(gross_profit) AS profit
        FROM views.sales_enriched
        WHERE sales_channel = 'Wholesale / reseller'
          AND order_date BETWEEN ? AND ?
        """,
        window,
    ).iloc[0]
    total = data.scalar(
        "SELECT SUM(net_sales) FROM views.sales_enriched WHERE order_date BETWEEN ? AND ?",
        window,
    )
    b2b = data.q(
        """
        SELECT COUNT(DISTINCT sales_order_id) AS orders,
               COUNT(DISTINCT customer_id) AS customers,
               SUM(net_sales) AS net,
               SUM(gross_profit) AS profit
        FROM views.sales_enriched
        WHERE customer_segment = 'B2B reseller'
          AND order_date BETWEEN ? AND ?
        """,
        window,
    ).iloc[0]
    new_accounts = data.scalar(
        """
        SELECT COUNT(*) FROM views.wholesale_accounts
        WHERE first_order_date BETWEEN ? AND ?
        """,
        window,
    )
    orders = int(wholesale.orders or 0)
    net = float(wholesale.net) if pd.notna(wholesale.net) else 0.0
    total_net = float(total) if total is not None else 0.0
    b2b_orders = int(b2b.orders or 0)
    b2b_net = float(b2b.net) if pd.notna(b2b.net) else 0.0
    return {
        "orders": orders,
        "customers": int(wholesale.customers or 0),
        "net": net,
        "profit": float(wholesale.profit) if pd.notna(wholesale.profit) else 0.0,
        "aov": net / orders if orders else 0.0,
        "share": net / total_net if total_net else 0.0,
        "total_net": total_net,
        "b2b_orders": b2b_orders,
        "b2b_customers": int(b2b.customers or 0),
        "b2b_net": b2b_net,
        "b2b_profit": float(b2b.profit) if pd.notna(b2b.profit) else 0.0,
        "b2b_aov": b2b_net / b2b_orders if b2b_orders else 0.0,
        "b2b_share": b2b_net / total_net if total_net else 0.0,
        "b2b_margin": (float(b2b.profit) / b2b_net)
        if pd.notna(b2b.profit) and b2b_net
        else 0.0,
        "new_accounts": int(new_accounts or 0),
    }


cur = _wholesale_kpis((start, end))
pri = _wholesale_kpis(prev_window) if prev_window else None

theme.page_header(
    "Wholesale & Distributor Performance",
    f"Reporting period: **{label}** · wholesale channel + B2B reseller segment · "
    f"{cur['new_accounts']:,} new B2B accounts · data through {DATA_END.isoformat()}",
    eyebrow="Growth",
    badges=('Sell-in only',),
)

cards = st.columns(4)
_card(
    cards[0], "Wholesale channel net", theme.fmt_egp(cur["net"]),
    _delta(cur["net"], _prior(pri, "net")),
    f"{cur['share']:.1%} of company net · {cur['customers']:,} buyers",
)
_card(
    cards[1], "Wholesale orders", theme.fmt_int(cur["orders"]),
    _delta(cur["orders"], _prior(pri, "orders")),
    f"AOV EGP {cur['aov']:,.0f} · wholesale channel",
)
_card(
    cards[2], "B2B reseller net", theme.fmt_egp(cur["b2b_net"]),
    _delta(cur["b2b_net"], _prior(pri, "b2b_net")),
    f"all channels · {cur['b2b_share']:.1%} of company net · margin {cur['b2b_margin']:.1%}",
)
_card(
    cards[3], "Active B2B accounts", theme.fmt_int(cur["b2b_customers"]),
    _delta(cur["b2b_customers"], _prior(pri, "b2b_customers")),
    f"{cur['new_accounts']:,} placed their first order in this window",
)

st.divider()

# ------------------------------------------------------------ channel trend --
trend = data.q(
    """
    WITH w AS (
        SELECT ym,
               COUNT(DISTINCT sales_order_id) AS orders,
               SUM(net_sales) AS net
        FROM views.sales_enriched
        WHERE sales_channel = 'Wholesale / reseller'
          AND order_date BETWEEN ? AND ?
        GROUP BY 1
    ),
    t AS (
        SELECT ym,
               SUM(net_sales) AS total_net
        FROM views.sales_enriched
        WHERE order_date BETWEEN ? AND ?
        GROUP BY 1
    )
    SELECT w.ym, w.orders, w.net, t.total_net,
           w.net / NULLIF(t.total_net, 0) AS share
    FROM w JOIN t USING (ym)
    ORDER BY w.ym
    """,
    (start, end, start, end),
)

trend_fig = go.Figure()
trend_fig.add_trace(go.Bar(
    x=trend.ym, y=trend.net,
    name="Wholesale net (EGP)", marker_color=theme.ACCENT,
    customdata=trend.orders,
    hovertemplate=(
        "%{x}: EGP %{y:,.0f}<br>%{customdata:,} orders<extra></extra>"
    ),
))
trend_fig.add_trace(go.Scatter(
    x=trend.ym, y=trend.share,
    name="Share of company net", mode="lines+markers", yaxis="y2",
    line={"color": theme.ACCENT_2, "width": 2},
    hovertemplate="%{x}: %{y:.1%} of company net<extra></extra>",
))
trend_fig.update_layout(
    title="Monthly wholesale net and share of company net",
    yaxis={"title": "Wholesale net (EGP)"},
    yaxis2={
        "title": "Share of company net", "overlaying": "y", "side": "right",
        "tickformat": ".1%", "dtick": 0.005, "showgrid": False,
    },
)
theme.apply_plotly_style(trend_fig)

governorates = data.q(
    """
    SELECT branch_governorate_ar AS governorate,
           COUNT(DISTINCT sales_order_id) AS orders,
           COUNT(DISTINCT customer_id) AS customers,
           SUM(net_sales) AS net
    FROM views.sales_enriched
    WHERE sales_channel = 'Wholesale / reseller'
      AND order_date BETWEEN ? AND ?
    GROUP BY 1 ORDER BY net DESC
    """,
    (start, end),
)
governorates["share"] = governorates.net / governorates.net.sum()
gov_top = governorates.head(12).sort_values("net")

gov_fig = go.Figure(go.Bar(
    x=gov_top.net, y=gov_top.governorate, orientation="h",
    marker_color=theme.ACCENT_2,
    text=[f"{share:.1%} · {orders:,}"
          for share, orders in zip(gov_top.share, gov_top.orders, strict=True)],
    textposition="outside", cliponaxis=False,
    customdata=gov_top[["customers", "share"]].to_numpy(),
    hovertemplate=(
        "%{y}<br>Net EGP %{x:,.0f}<br>%{customdata[0]:,} buyers"
        "<br>%{customdata[1]:.1%} of wholesale net<extra></extra>"
    ),
))
gov_fig.update_layout(title="Top 12 branch governorates - wholesale net")
theme.apply_plotly_style(gov_fig)
gov_fig.update_xaxes(range=[0, float(gov_top.net.max()) * 1.22])
gov_fig.update_yaxes(autorange="reversed")

chart_l, chart_r = st.columns(2)
with chart_l:
    st.plotly_chart(trend_fig, width="stretch", config={"displayModeBar": False})
with chart_r:
    st.plotly_chart(gov_fig, width="stretch", config={"displayModeBar": False})
st.caption(
    "Wholesale orders are attributed to the selling branch's governorate; the data "
    "has no distributor ship-to address on the order. Governorate labels show share "
    "of wholesale net · order count."
)

# ------------------------------------------------------ category & accounts --
categories = data.q(
    """
    SELECT category_en,
           SUM(quantity) AS units,
           SUM(net_sales) AS net
    FROM views.sales_enriched
    WHERE sales_channel = 'Wholesale / reseller'
      AND order_date BETWEEN ? AND ?
    GROUP BY 1 ORDER BY net DESC
    """,
    (start, end),
)
if len(categories) > 8:
    other = pd.DataFrame({
        "category_en": ["Other categories"],
        "units": [categories.iloc[8:].units.sum()],
        "net": [categories.iloc[8:].net.sum()],
    })
    categories = pd.concat([categories.head(8), other], ignore_index=True)

cat_fig = go.Figure(go.Pie(
    labels=categories.category_en,
    values=categories.net,
    hole=0.55,
    marker={"colors": theme.COLORS + ["#94A3B8", "#64748B"]},
    textinfo="percent",
    customdata=categories.units,
    hovertemplate="%{label}<br>Net EGP %{value:,.0f}<br>%{customdata:,} units<extra></extra>",
))
cat_fig.update_layout(title="Wholesale category mix (top 8 + other)")
theme.apply_plotly_style(cat_fig)

quartiles = data.q(
    """
    WITH p AS (
        SELECT customer_id,
               COUNT(DISTINCT sales_order_id) AS orders,
               SUM(net_sales) AS net
        FROM views.sales_enriched
        WHERE customer_segment = 'B2B reseller'
          AND order_date BETWEEN ? AND ?
        GROUP BY 1
    )
    SELECT a.net_quartile,
           COUNT(*) AS accounts,
           SUM(p.orders) AS orders,
           SUM(p.net) AS net
    FROM p JOIN views.wholesale_accounts a USING (customer_id)
    GROUP BY 1 ORDER BY 1
    """,
    (start, end),
)

quartile_fig = go.Figure(go.Bar(
    x=quartiles.net_quartile.astype(str),
    y=quartiles.net,
    marker_color=theme.ACCENT,
    text=[f"{accounts:,} accounts" for accounts in quartiles.accounts],
    textposition="outside", cliponaxis=False,
    customdata=quartiles[["accounts", "orders"]].to_numpy(),
    hovertemplate=(
        "Quartile %{x}<br>Net EGP %{y:,.0f}<br>%{customdata[0]:,} accounts"
        "<br>%{customdata[1]:,} orders<extra></extra>"
    ),
))
quartile_fig.update_layout(
    title="B2B net by all-time account quartile (1 = largest)",
    xaxis={"title": "All-time net quartile"},
    yaxis={"title": "Net in window (EGP)"},
)
theme.apply_plotly_style(quartile_fig)

cat_col, quartile_col = st.columns(2)
with cat_col:
    st.plotly_chart(cat_fig, width="stretch", config={"displayModeBar": False})
with quartile_col:
    st.plotly_chart(quartile_fig, width="stretch", config={"displayModeBar": False})
st.caption(
    "Account quartiles are based on all-time B2B net in `views.wholesale_accounts`; "
    "the bars show how much those account tiers bought in the selected window."
)

# ------------------------------------------------------------- account table --
st.subheader("B2B reseller accounts in the window")
accounts = data.q(
    """
    WITH p AS (
        SELECT customer_id,
               COUNT(DISTINCT sales_order_id) AS orders,
               SUM(quantity) AS units,
               SUM(net_sales) AS net,
               SUM(gross_profit) AS profit
        FROM views.sales_enriched
        WHERE customer_segment = 'B2B reseller'
          AND order_date BETWEEN ? AND ?
        GROUP BY 1
    )
    SELECT p.customer_id,
           a.customer_name_ar AS account,
           a.governorate_ar AS governorate,
           p.orders, p.units, p.net, p.profit,
           p.net / NULLIF(p.orders, 0) AS aov,
           p.profit / NULLIF(p.net, 0) AS margin,
           a.primary_channel,
           a.recency_bucket,
           a.net_quartile,
           a.first_order_date
    FROM p
    LEFT JOIN views.wholesale_accounts a USING (customer_id)
    ORDER BY p.net DESC
    """,
    (start, end),
)
top10_share = accounts.head(10).net.sum() / accounts.net.sum() if accounts.net.sum() else 0.0
accounts["margin"] = accounts.margin * 100

st.dataframe(
    accounts.head(25),
    hide_index=True,
    column_config={
        "customer_id": st.column_config.TextColumn("Account ID", width="small"),
        "account": st.column_config.TextColumn("Account"),
        "governorate": st.column_config.TextColumn("Governorate", width="small"),
        "orders": st.column_config.NumberColumn("Orders", format="%.0f", width="small"),
        "units": st.column_config.NumberColumn("Units", format="%.0f"),
        "net": st.column_config.NumberColumn("Net (EGP)", format="%.0f"),
        "profit": st.column_config.NumberColumn("Gross profit (EGP)", format="%.0f"),
        "aov": st.column_config.NumberColumn("AOV (EGP)", format="%.0f"),
        "margin": st.column_config.NumberColumn("Margin (%)", format="%.1f"),
        "primary_channel": st.column_config.TextColumn("Primary channel", width="small"),
        "recency_bucket": st.column_config.TextColumn("Recency (as of data end)", width="small"),
        "net_quartile": st.column_config.NumberColumn("All-time quartile", format="%.0f", width="small"),
        "first_order_date": st.column_config.DateColumn("First order"),
    },
)
st.caption(
    f"Top 25 of {len(accounts):,} active B2B accounts in the window. "
    f"The top 10 accounts account for {top10_share:.1%} of B2B net. "
    "Recency and quartile are all-time profile facts as of the dataset end."
)

with st.expander("Data notes - definitions & caveats for this page", expanded=False):
    st.markdown(
        f"""
- **Two different scopes, kept separate**:
  - **Wholesale channel** = `sales_channel = 'Wholesale / reseller'` (54,169 orders,
    EGP 319.6M all-time). It includes Retail, Guest and B2B buyers.
  - **B2B reseller segment** = `customer_segment = 'B2B reseller'` (1,476 accounts,
    8,587 orders, EGP 13.2M all-time). B2B customers mostly buy through Retail POS
    and E-commerce, so this is **not** a subset of the wholesale channel.
- **No distributor accounts table**: `views.wholesale_accounts` is built by
  aggregating real B2B customer orders. Account names come from `raw.customers`
  ("wholesale trader NNNNNN"); contract, credit-limit, distributor-tier and
  sell-out/sell-through fields do not exist.
- **Sell-in only**: net sales are Cottonil's sales to the reseller. There is no
  reseller inventory, sell-out, or end-consumer demand data.
- **Account value** = net sales on order dates in the selected window. Gross profit
  is the recorded line margin. Account recency and net quartile are all-time facts
  as of {DATA_END.isoformat()}, not recomputed per window.
- **Geography** is the selling branch governorate for the channel charts. The
  account table uses the customer's registered governorate.
- **AOV** = net sales / distinct orders. Active accounts = distinct B2B customer
  IDs with at least one order in the window. A "new" account placed its first
  dataset order inside the window.
- **Currency**: EGP, pre-VAT net line values.
"""
    )
