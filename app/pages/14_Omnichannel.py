"""Omnichannel (Lite) (S14) - three real sales channels, no invented funnels.

The dataset has Retail POS, Wholesale/reseller and E-commerce orders. It has no
sessions, carts, app users, marketplace feeds or attribution paths, so this page
measures channel mix and observed cross-channel customers only.
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import plotly.graph_objects as go
import streamlit as st

from app import data, theme
from app.filters import DATA_END, render_period_selector

st.set_page_config(
    page_title="Omnichannel · Cottonil",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.apply_theme()

start, end, label, _ = render_period_selector()
ym_start, ym_end = start.strftime("%Y-%m"), end.strftime("%Y-%m")

CHANNELS = ["Retail POS", "Wholesale / reseller", "E-commerce"]
CHANNEL_COLORS = {
    "Retail POS": theme.ACCENT,
    "Wholesale / reseller": theme.ACCENT_2,
    "E-commerce": theme.WARN,
}

trend = data.q(
    """
    SELECT ym, sales_channel, net_sales, orders, units
    FROM views.channel_monthly
    WHERE ym BETWEEN ? AND ?
    ORDER BY ym, sales_channel
    """,
    (ym_start, ym_end),
)

channel_kpis = data.q(
    """
    SELECT sales_channel,
           COUNT(DISTINCT sales_order_id)                    AS orders,
           COUNT(DISTINCT customer_id)                       AS customers,
           SUM(quantity)                                     AS units_sold,
           SUM(gross_sales)                                  AS gross_sales,
           SUM(discount)                                     AS discount,
           SUM(net_sales)                                    AS net_sales,
           SUM(gross_profit)                                 AS gross_profit
    FROM views.sales_enriched
    WHERE order_date BETWEEN ? AND ?
    GROUP BY 1
    """,
    (start, end),
)
channel_kpis = channel_kpis.set_index("sales_channel").reindex(
    [channel for channel in CHANNELS if channel in set(channel_kpis.sales_channel)]
).reset_index()
channel_kpis["aov"] = channel_kpis.net_sales / channel_kpis.orders.replace(0, 1)
channel_kpis["gross_margin"] = channel_kpis.gross_profit / channel_kpis.net_sales
channel_kpis["discount_rate"] = channel_kpis.discount / channel_kpis.gross_sales

total_net = float(channel_kpis.net_sales.sum())
total_orders = int(channel_kpis.orders.sum())
ecom = channel_kpis.loc[channel_kpis.sales_channel == "E-commerce"]
ecom_share = float(ecom.net_sales.iloc[0]) / total_net if len(ecom) and total_net else 0.0

cross = data.q(
    """
    WITH per_customer AS (
        SELECT customer_id,
               COUNT(DISTINCT sales_channel) AS channels,
               SUM(net_sales) AS net_sales
        FROM views.sales_enriched
        WHERE customer_id IS NOT NULL
          AND order_date BETWEEN ? AND ?
        GROUP BY 1
    )
    SELECT channels, COUNT(*) AS customers, SUM(net_sales) AS net_sales
    FROM per_customer
    GROUP BY 1
    ORDER BY 1
    """,
    (start, end),
)
cross_customers = int(cross.customers.sum())
multi = cross[cross.channels >= 2]
multi_customers = int(multi.customers.sum())
multi_revenue_share = float(multi.net_sales.sum()) / total_net if total_net else 0.0

returns = data.q(
    """
    WITH orders AS (
        SELECT sales_channel, COUNT(DISTINCT sales_order_id) AS orders
        FROM views.sales_enriched
        WHERE order_date BETWEEN ? AND ?
        GROUP BY 1
    ),
    returned AS (
        SELECT sales_channel, COUNT(DISTINCT sales_order_id) AS returned_orders
        FROM views.returns_enriched
        WHERE return_date BETWEEN ? AND ?
        GROUP BY 1
    )
    SELECT o.sales_channel,
           COALESCE(r.returned_orders, 0)                   AS returned_orders,
           COALESCE(r.returned_orders, 0) / NULLIF(o.orders, 0) AS return_rate
    FROM orders o
    LEFT JOIN returned r USING (sales_channel)
    """,
    (start, end, start, end),
)
channel_kpis = channel_kpis.merge(returns, on="sales_channel", how="left")
channel_kpis["returned_orders"] = channel_kpis["returned_orders"].fillna(0)
channel_kpis["return_rate"] = channel_kpis["return_rate"].fillna(0)
overall_returns = float(channel_kpis.returned_orders.sum())
overall_return_rate = overall_returns / total_orders if total_orders else 0.0

theme.page_header(
    "Omnichannel",
    f"Reporting period: **{label}** · three real sales channels · "
    f"observed customers only (guests excluded from customer metrics, audit A4) · "
    f"data through {DATA_END.isoformat()}",
    eyebrow="Growth",
    badges=('Observed customers only',),
)

cards = st.columns(4)
with cards[0]:
    theme.kpi_card(
        "Net sales · all channels",
        theme.fmt_egp(total_net),
        sub=f"{theme.fmt_int(total_orders)} orders · {theme.fmt_int(float(channel_kpis.units_sold.sum()))} units",
    )
with cards[1]:
    theme.kpi_card(
        "E-commerce share",
        f"{ecom_share:.1%}",
        sub="of net sales · online is the smallest of the three channels",
    )
with cards[2]:
    theme.kpi_card(
        "Multi-channel customers",
        f"{multi_customers / cross_customers:.1%}" if cross_customers else "n/a",
        sub=(
            f"{multi_customers:,} of {cross_customers:,} identified buyers · "
            f"{multi_revenue_share:.1%} of net sales"
        ),
    )
with cards[3]:
    theme.kpi_card(
        "Return rate",
        f"{overall_return_rate:.1%}",
        sub=f"{theme.fmt_int(overall_returns)} returned orders / orders in window",
    )

st.divider()

# ------------------------------------------------------------ monthly channel mix --
pivot = trend.pivot(index="ym", columns="sales_channel", values="net_sales").fillna(0)
channels_present = [channel for channel in CHANNELS if channel in pivot.columns]
stack = go.Figure()
for channel in channels_present:
    stack.add_trace(
        go.Bar(
            x=pivot.index,
            y=pivot[channel],
            name=channel,
            marker_color=CHANNEL_COLORS[channel],
            hovertemplate="%{x}<br>EGP %{y:,.0f}<extra>%{fullData.name}</extra>",
        )
    )
stack.update_layout(
    title="Monthly net sales by channel",
    barmode="stack",
    yaxis_title="Net sales (EGP)",
    xaxis_title="Month",
)
theme.apply_plotly_style(stack)
st.plotly_chart(stack, width="stretch", config={"displayModeBar": False})

left, right = st.columns((2, 3))

with left:
    share = go.Figure(
        go.Pie(
            hole=0.55,
            labels=channel_kpis.sales_channel,
            values=channel_kpis.net_sales,
            marker={"colors": [CHANNEL_COLORS[c] for c in channel_kpis.sales_channel]},
            textinfo="percent",
            customdata=channel_kpis.net_sales,
            hovertemplate="%{label}<br>EGP %{customdata:,.0f} (%{percent})<extra></extra>",
        )
    )
    share.update_layout(title="Net-sales share")
    theme.apply_plotly_style(share)
    st.plotly_chart(share, width="stretch", config={"displayModeBar": False})

with right:
    cross_labels = [
        f"{int(row.channels)} channel" + ("s" if int(row.channels) != 1 else "")
        for row in cross.itertuples()
    ]
    cross_fig = go.Figure()
    cross_fig.add_trace(
        go.Bar(
            x=cross_labels,
            y=cross.customers / cross.customers.sum(),
            name="Share of customers",
            marker_color=theme.ACCENT,
            customdata=cross.customers,
            hovertemplate="%{x}<br>%{customdata:,} customers (%{y:.1%})<extra></extra>",
        )
    )
    cross_fig.add_trace(
        go.Bar(
            x=cross_labels,
            y=cross.net_sales / cross.net_sales.sum(),
            name="Share of net sales",
            marker_color=theme.ACCENT_2,
            customdata=cross.net_sales,
            hovertemplate="%{x}<br>EGP %{customdata:,.0f} (%{y:.1%})<extra></extra>",
        )
    )
    cross_fig.update_layout(
        title="Observed cross-channel behaviour in the window",
        barmode="group",
        yaxis={"title": "Share", "tickformat": ".0%"},
        xaxis_title="Distinct channels used",
    )
    theme.apply_plotly_style(cross_fig)
    st.plotly_chart(cross_fig, width="stretch", config={"displayModeBar": False})
    st.caption(
        "Counts only customers with a non-null id. A customer who bought in two "
        "channels is multi-channel for this window; no cross-device or identity "
        "stitching is available."
    )

st.divider()

# ------------------------------------------------------------- channel economics --
theme.section_header("Channel economics")
table = channel_kpis[
    [
        "sales_channel",
        "orders",
        "customers",
        "units_sold",
        "net_sales",
        "aov",
        "gross_margin",
        "discount_rate",
        "return_rate",
    ]
].copy()
for column in ("gross_margin", "discount_rate", "return_rate"):
    table[column] *= 100
st.dataframe(
    table,
    hide_index=True,
    column_config={
        "sales_channel": st.column_config.TextColumn("Channel"),
        "orders": st.column_config.NumberColumn("Orders", format="%.0f"),
        "customers": st.column_config.NumberColumn("Customers", format="%.0f"),
        "units_sold": st.column_config.NumberColumn("Units", format="%.0f"),
        "net_sales": st.column_config.NumberColumn("Net sales (EGP)", format="%.0f"),
        "aov": st.column_config.NumberColumn("AOV (EGP)", format="%.0f"),
        "gross_margin": st.column_config.NumberColumn("Gross margin (%)", format="%.1f"),
        "discount_rate": st.column_config.NumberColumn("Discount (%)", format="%.1f"),
        "return_rate": st.column_config.NumberColumn("Return rate (%)", format="%.1f"),
    },
)
st.caption(
    "Customer counts per channel overlap: one customer can buy in more than one "
    "channel. Return rate is a period ratio (returns by return date / orders by "
    "order date), not a cohort rate."
)

with st.expander("Scope limits: what 'omnichannel' means here (S14)", expanded=False):
    st.markdown(
        "- **Real**: Retail POS, Wholesale/reseller and E-commerce order lines; "
        "channel mix, AOV, margin, discounts, returns and observed multi-channel "
        "customers.\n"
        "- **Not in the dataset**: website sessions, funnels, carts, app users, "
        "marketplace feeds, click-and-collect, ship-from-store, cross-device "
        "identity, or channel-level acquisition cost.\n"
        "- **Guest checkout** (~19% of orders, audit A4) counts in revenue and "
        "orders but has no customer_id, so it is absent from customer and "
        "cross-channel metrics.\n"
        "- **Channel is the order channel**, not the marketing channel. Campaign "
        "spend and rebuilt attribution live on the Marketing ROI page (audit A2).\n"
        "- A B2B reseller can transact through Retail POS or E-commerce; the "
        "Wholesale channel is a separate order channel, not the same as the B2B "
        "customer segment."
    )
