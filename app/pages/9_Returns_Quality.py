"""Returns & Quality Control (S10).

Scope matrix S10: returns, reasons and refunds are real; there is no inspection
funnel, claims workflow, or defect-stage data. Refunds always use refund_capped
(audit A3), and return rate is shown on a return-date basis.
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
    page_title="Returns & Quality · Cottonil",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.apply_theme()

start, end, label, mode = render_period_selector()
prev_window = previous_period(start, end, mode)
prev_label = window_label(prev_window, empty="no comparison window")
_delta = partial(delta_label, label=prev_label)

channels = data.q(
    "SELECT DISTINCT sales_channel FROM views.returns_enriched ORDER BY 1"
).iloc[:, 0].tolist()
channel = st.sidebar.selectbox("Sales channel", ["All channels", *channels])
channel_sql = "" if channel == "All channels" else " AND sales_channel = ?"


def _params(window: tuple) -> tuple:
    params: tuple = tuple(window)
    if channel != "All channels":
        params += (channel,)
    return params


def _prior(prior: dict | None, key: str):
    return None if prior is None else prior[key]


def _card(col, title: str, value: str, delta: tuple, sub: str) -> None:
    text, up, good = delta
    with col:
        theme.kpi_card(title, value, delta=text, delta_up=up, delta_good=good, sub=sub)


# --------------------------------------------------------------- return KPIs --
def _returns_kpis(window: tuple) -> dict:
    params = _params(window)
    r = data.q(
        """
        SELECT COUNT(*) AS returns,
               COUNT(DISTINCT sales_order_id) AS returned_orders,
               SUM(return_quantity) AS units,
               SUM(refund_capped) AS refund,
               COUNT(*) FILTER (WHERE reason = 'Defect claim') AS defect_returns,
               SUM(refund_capped) FILTER (WHERE reason = 'Defect claim') AS defect_refund
        FROM views.returns_enriched
        WHERE return_date BETWEEN ? AND ?
        """
        + channel_sql,
        params,
    ).iloc[0]
    o = data.q(
        """
        SELECT COUNT(DISTINCT sales_order_id) AS orders,
               SUM(net_sales) AS net
        FROM views.sales_enriched
        WHERE order_date BETWEEN ? AND ?
        """
        + channel_sql,
        params,
    ).iloc[0]
    returns = int(r.returns or 0)
    refund = float(r.refund) if pd.notna(r.refund) else 0.0
    orders = int(o.orders or 0)
    net = float(o.net) if pd.notna(o.net) else 0.0
    return {
        "returns": returns,
        "returned_orders": int(r.returned_orders or 0),
        "units": int(r.units or 0),
        "refund": refund,
        "defect_returns": int(r.defect_returns or 0),
        "defect_refund": float(r.defect_refund) if pd.notna(r.defect_refund) else 0.0,
        "defect_share": int(r.defect_returns or 0) / returns if returns else 0.0,
        "orders": orders,
        "net": net,
        "return_rate": int(r.returned_orders or 0) / orders if orders else 0.0,
        "refund_rate": refund / net if net else 0.0,
        "avg_refund": refund / returns if returns else 0.0,
    }


cur = _returns_kpis((start, end))
pri = _returns_kpis(prev_window) if prev_window else None

theme.page_header(
    "Returns & Quality Control",
    f"Reporting period: **{label}** · {cur['returns']:,} returns · "
    f"refunds capped at line value (A3) · data through {DATA_END.isoformat()}",
    eyebrow="Operations",
    badges=('Refunds capped at line value',),
)

cards = st.columns(4)
_card(
    cards[0], "Returns", theme.fmt_int(cur["returns"]),
    _delta(cur["returns"], _prior(pri, "returns"), lower_is_better=True),
    f"{cur['returned_orders']:,} orders · {cur['units']:,} units",
)
_card(
    cards[1], "Refund (capped)", theme.fmt_egp(cur["refund"]),
    _delta(cur["refund"], _prior(pri, "refund"), lower_is_better=True),
    f"{cur['refund_rate']:.2%} of net sales · avg EGP {cur['avg_refund']:,.0f} per return",
)
_card(
    cards[2], "Return rate", theme.fmt_pct(cur["return_rate"]),
    _delta(cur["return_rate"], _prior(pri, "return_rate"), lower_is_better=True),
    f"{cur['returned_orders']:,} returned / {cur['orders']:,} orders in window",
)
_card(
    cards[3], "Defect claims", theme.fmt_int(cur["defect_returns"]),
    _delta(cur["defect_returns"], _prior(pri, "defect_returns"), lower_is_better=True),
    f"{cur['defect_share']:.1%} of returns · no inspection funnel",
)

st.divider()

# ---------------------------------------------------------------- trends ----
trend = data.q(
    """
    WITH r AS (
        SELECT ym,
               COUNT(*) AS returns,
               COUNT(DISTINCT sales_order_id) AS returned_orders,
               SUM(refund_capped) AS refund
        FROM views.returns_enriched
        WHERE return_date BETWEEN ? AND ?
        """
    + channel_sql
    + """
        GROUP BY 1
    ),
    o AS (
        SELECT ym,
               COUNT(DISTINCT sales_order_id) AS orders,
               SUM(net_sales) AS net
        FROM views.sales_enriched
        WHERE order_date BETWEEN ? AND ?
        """
    + channel_sql
    + """
        GROUP BY 1
    )
    SELECT r.ym, r.returns, r.returned_orders, r.refund,
           o.orders, o.net,
           r.returned_orders / NULLIF(o.orders, 0) AS return_rate
    FROM r LEFT JOIN o USING (ym)
    ORDER BY r.ym
    """,
    _params((start, end)) + _params((start, end)),
)
trend["return_rate"] = trend.return_rate.fillna(0.0)

trend_fig = go.Figure()
trend_fig.add_trace(go.Bar(
    x=trend.ym, y=trend.returns,
    name="Returns", marker_color=theme.ACCENT,
    customdata=trend.refund,
    hovertemplate="%{x}: %{y:,} returns<br>Refund EGP %{customdata:,.0f}<extra></extra>",
))
trend_fig.add_trace(go.Scatter(
    x=trend.ym, y=trend.return_rate,
    name="Return rate", mode="lines+markers", yaxis="y2",
    line={"color": theme.BAD, "width": 2},
    hovertemplate="%{x}: %{y:.2%} of orders<extra></extra>",
))
trend_fig.update_layout(
    title="Monthly returns and return rate",
    yaxis={"title": "Returns"},
    yaxis2={
        "title": "Return rate", "overlaying": "y", "side": "right",
        "tickformat": ".1%", "dtick": 0.01, "showgrid": False,
    },
)
theme.apply_plotly_style(trend_fig)

reasons = data.q(
    """
    SELECT reason,
           COUNT(*) AS returns,
           SUM(refund_capped) AS refund,
           AVG(refund_capped) AS avg_refund
    FROM views.returns_enriched
    WHERE return_date BETWEEN ? AND ?
    """
    + channel_sql
    + " GROUP BY 1 ORDER BY refund DESC",
    _params((start, end)),
)

reason_fig = go.Figure(go.Pie(
    labels=reasons.reason,
    values=reasons.refund,
    hole=0.55,
    marker={"colors": theme.COLORS},
    textinfo="percent",
    customdata=reasons[["returns", "avg_refund"]].to_numpy(),
    hovertemplate=(
        "%{label}<br>Refund EGP %{value:,.0f}<br>%{customdata[0]:,} returns"
        "<br>Avg refund EGP %{customdata[1]:,.0f}<extra></extra>"
    ),
))
reason_fig.update_layout(title="Refund share by reason")
theme.apply_plotly_style(reason_fig)

chart_l, chart_r = st.columns(2)
with chart_l:
    st.plotly_chart(trend_fig, width="stretch", config={"displayModeBar": False})
with chart_r:
    st.plotly_chart(reason_fig, width="stretch", config={"displayModeBar": False})
st.caption(
    "Return rate uses return dates in the numerator and order dates in the denominator; "
    "it is a period ratio, not a cohort rate."
)

# ------------------------------------------------- categories & branches ----
category = data.q(
    """
    WITH r AS (
        SELECT category_en,
               COUNT(*) AS returns,
               SUM(refund_capped) AS refund
        FROM views.returns_enriched
        WHERE return_date BETWEEN ? AND ?
        """
    + channel_sql
    + """
        GROUP BY 1
    ),
    s AS (
        SELECT category_en,
               SUM(net_sales) AS net
        FROM views.sales_enriched
        WHERE order_date BETWEEN ? AND ?
        """
    + channel_sql
    + """
        GROUP BY 1
    )
    SELECT r.category_en, r.returns, r.refund, s.net,
           r.refund / NULLIF(s.net, 0) AS refund_rate
    FROM r LEFT JOIN s USING (category_en)
    ORDER BY r.refund DESC
    """,
    _params((start, end)) + _params((start, end)),
)
category["refund_rate"] = category.refund_rate.fillna(0.0)
category_plot = category.sort_values("refund")

category_fig = go.Figure(go.Bar(
    x=category_plot.refund, y=category_plot.category_en, orientation="h",
    marker_color=theme.ACCENT,
    text=[f"{rate:.1%}" for rate in category_plot.refund_rate],
    textposition="outside", cliponaxis=False,
    customdata=category_plot[["returns", "refund_rate"]].to_numpy(),
    hovertemplate=(
        "%{y}<br>Refund EGP %{x:,.0f}<br>%{customdata[0]:,} returns"
        "<br>Refund / category net %{customdata[1]:.2%}<extra></extra>"
    ),
))
category_fig.update_layout(title="Refund by category - labels show % of category net")
theme.apply_plotly_style(category_fig)
category_fig.update_xaxes(title="Refund (EGP, capped)")

governorates = data.q(
    """
    SELECT branch_governorate_ar AS governorate,
           COUNT(*) AS returns,
           COUNT(DISTINCT sales_order_id) AS orders,
           SUM(refund_capped) AS refund
    FROM views.returns_enriched
    WHERE return_date BETWEEN ? AND ?
    """
    + channel_sql
    + " GROUP BY 1 ORDER BY refund DESC LIMIT 10",
    _params((start, end)),
)

cat_col, gov_col = st.columns(2)
with cat_col:
    st.plotly_chart(category_fig, width="stretch", config={"displayModeBar": False})
with gov_col:
    st.markdown("##### Top 10 branch governorates by refund")
    st.dataframe(
        governorates,
        hide_index=True,
        column_config={
            "governorate": st.column_config.TextColumn("Governorate"),
            "returns": st.column_config.NumberColumn("Returns", format="%.0f"),
            "orders": st.column_config.NumberColumn("Returned orders", format="%.0f"),
            "refund": st.column_config.NumberColumn("Refund (EGP, capped)", format="%.0f"),
        },
    )
    st.caption(
        "Branch governorate of the original sale line, not the customer's address. "
        "Only categories with a matching sale in the same window get a refund rate."
    )

with st.expander("Data notes - definitions & caveats for this page", expanded=False):
    st.markdown(
        f"""
- **Grain**: `views.returns_enriched` is one row per return (28,500 rows,
  2018-10 → {DATA_END.isoformat()}), joined to the original sales line.
- **Audit A3 - refund cap**: all refund figures use `refund_capped =
  LEAST(refund_amount, line net)`. The raw refund exceeds line value on a small
  number of rows; the cap prevents overstating refunds.
- **Return rate** = distinct returned orders in the window ÷ distinct orders in the
  window. The numerator uses **return date**, the denominator uses **order date**,
  so this is a period ratio, not a same-cohort return rate. It is not annualized.
- **Refund / category net** compares refunds on return dates with category net on
  order dates in the same window; read it as a directional intensity, not a cohort
  margin hit. Categories with no sales in the window show no rate.
- **Reasons**: `Other`, `Defect claim`, `Exchange`, `Wrong item`, `Size issue`.
  `Defect claim` is a **self-reported reason label**. There is no inspection stage,
  defect code, supplier claim, repair/rework record, or claims funnel in the data.
- **Returns channel** is the channel of the original sale. Guest orders are
  included in money metrics (audit A4), but customer identity is not available.
- **Currency**: EGP, pre-VAT line values. Refunds are money returned to customers,
  not net sales.
"""
    )
