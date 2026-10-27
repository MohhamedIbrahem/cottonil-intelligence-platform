"""Executive Overview (deck p.2) - the board-level landing of KPIs.

US2 / tasks T040-T044. Every figure comes from views.* read-only; YoY compares
the same calendar-span one year earlier (filters.previous_period), never a
naive prior slice. The old Home hero + all-time strip and the platform data
notes were folded in here; the grouped sidebar replaces the old roadmap grid.
"""

from __future__ import annotations

import sys
from functools import partial
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))  # pages/ -> app/ -> repo root

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

theme.page_header(
    "Executive Overview",
    f"Reporting period: **{label}** · figures include guest checkout (audit A4) "
    f"· data through {DATA_END.isoformat()}",
    eyebrow="Core performance",
    badges=('Board view',),
)

# ------------------------------------ company at a glance (folded from Home) --
theme.section_header(
    "Company at a glance",
    "All-time figures from the curated views — these do NOT change with the "
    "reporting period; the board view below does.",
    eyebrow="Overview",
)
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
        sub=f"excl. 14% VAT · {float(_head.months):,.0f} months of data",
        tone="blue",
    )
with c2:
    theme.kpi_card(
        "Orders · all time",
        theme.fmt_int(float(_head.orders)),
        sub="line-level spine: views.sales_enriched",
        tone="teal",
    )
with c3:
    theme.kpi_card(
        "Customers",
        theme.fmt_int(float(_dims.customers)),
        sub=f"{theme.fmt_int(float(_dims.buyers))} with ≥1 order "
        f"({float(_dims.buyers) / float(_dims.customers):.0%}) - rest are catalog-only",
        tone="violet",
    )
with c4:
    theme.kpi_card(
        "Branches",
        theme.fmt_int(float(_dims.branches)),
        sub=f"across {int(_dims.governorates)} governorates",
        tone="rose",
    )

st.divider()


# ----------------------------------------------------------------- queries ---
def _kpi_row(window: tuple) -> pd.Series:  # type: ignore[type-arg]
    s, e = window
    net = data.q(
        """
        SELECT SUM(net_sales) AS net, SUM(gross_profit) AS gross_profit,
               COUNT(DISTINCT sales_order_id) AS orders,
               COUNT(DISTINCT customer_id) AS customers
        FROM views.sales_enriched
        WHERE order_date BETWEEN ? AND ?
        """,
        (s, e),
    ).iloc[0]
    returned = data.scalar(
        """
        SELECT COUNT(DISTINCT le.sales_order_id)
        FROM views.returns_enriched r
        JOIN views.sales_enriched le ON le.sales_order_id = r.sales_order_id
        WHERE le.order_date BETWEEN ? AND ?
        """,
        (s, e),
    )
    net["returned_orders"] = int(returned or 0)
    return net


cur = _kpi_row((start, end))
prior = _kpi_row(prev_window) if prev_window else None
prev_label = window_label(prev_window, empty="no comparison window")
_delta = partial(delta_label, label=prev_label)


rate_cur = float(cur.returned_orders) / max(float(cur.orders), 1)
if prior is None or float(prior.orders) == 0:
    rate_delta = ("n/a", True, False)
else:
    rate_prev = float(prior.returned_orders) / float(prior.orders)
    rate_delta = _delta(rate_cur, rate_prev, lower_is_better=True)

kpi_cards = [
    ("Net sales (excl. VAT)", theme.fmt_egp(float(cur.net)),
     _delta(cur.net, None if prior is None else prior.net), "EGP after discounts", "blue"),
    ("Gross profit", theme.fmt_egp(float(cur.gross_profit)),
     _delta(cur.gross_profit, None if prior is None else prior.gross_profit),
     "margin_EGP as recorded (deck: 'الربح')", "green"),
    ("Orders", theme.fmt_int(float(cur.orders)),
     _delta(cur.orders, None if prior is None else prior.orders),
     "distinct order heads in window", "teal"),
    ("Active customers", theme.fmt_int(float(cur.customers)),
     _delta(cur.customers, None if prior is None else prior.customers),
     "distinct logged-in buyers (guests excluded by definition, A4)", "violet"),
    ("Return rate", theme.fmt_pct(rate_cur), rate_delta,
     "orders with \u22651 return / all placed orders", "red"),
]

cols = st.columns(5)
for col, (title, value, delta, sub, tone) in zip(cols, kpi_cards, strict=True):
    with col:
        theme.kpi_card(title, value, delta=delta[0], delta_up=delta[1], delta_good=delta[2], sub=sub, tone=tone)

st.divider()

# ------------------------------------------------------- monthly trend (T041) --
trend = data.q(
    """
    SELECT ym, SUM(net_sales) AS net, SUM(gross_profit) AS gross_profit
    FROM views.sales_enriched
    WHERE order_date BETWEEN ? AND ?
    GROUP BY ym ORDER BY ym
    """,
    (start, end),
)
trend["month"] = pd.to_datetime(trend.ym + "-01")

trend_fig = go.Figure()
trend_fig.add_trace(go.Scatter(
    x=trend.month, y=trend.net, name="Net sales",
    mode="lines+markers", line={"width": 3, "color": theme.ACCENT},
    fill="tozeroy", fillcolor=theme.ACCENT_SOFT,
    hovertemplate="%{x|%b %Y}: EGP %{y:,.0f}<extra></extra>",
))
trend_fig.add_trace(go.Scatter(
    x=trend.month, y=trend.gross_profit, name="Gross profit",
    mode="lines+markers", line={"width": 2, "color": theme.WARN},
    hovertemplate="%{x|%b %Y}: EGP %{y:,.0f}<extra></extra>",
))
trend_fig.update_layout(title="Monthly sales & profit", showlegend=True)
theme.apply_plotly_style(trend_fig)
trend_fig.update_xaxes(tickformat="%b %Y")
st.plotly_chart(trend_fig, width="stretch", config={"displayModeBar": False})

# ------------------------------------------- branches & governorates (T042) --
branches = data.q(
    """
    SELECT branch_name_ar, branch_governorate_ar AS governorate,
           SUM(net_sales) AS net, COUNT(DISTINCT sales_order_id) AS orders
    FROM views.sales_enriched
    WHERE order_date BETWEEN ? AND ?
    GROUP BY 1, 2 ORDER BY net DESC
    """,
    (start, end),
)
top5 = branches.head(5).copy()
top5["label"] = [f"{n} · {g}" for n, g in zip(top5.branch_name_ar, top5.governorate, strict=True)]

b_col, g_col = st.columns([2, 3])

b_fig = go.Figure(go.Bar(
    x=top5.net, y=top5.label, orientation="h",
    marker={"color": theme.ACCENT},
    text=[theme.fmt_egp(v) for v in top5.net], textposition="inside",
    hovertemplate="%{y}: EGP %{x:,.0f}<extra></extra>",
))
b_fig.update_layout(title="Top-5 branches by net sales")
theme.apply_plotly_style(b_fig)
b_fig.update_yaxes(autorange="reversed")

gov_totals = (
    branches.groupby("governorate", as_index=False)["net"].sum()
    .sort_values("net", ascending=False)
)
gov_totals["share"] = gov_totals.net / gov_totals.net.sum()
g_fig = go.Figure(go.Bar(
    x=gov_totals.governorate, y=gov_totals.share,
    marker={"color": theme.ACCENT_2},
    text=[theme.fmt_pct(s) for s in gov_totals.share], textposition="outside",
    cliponaxis=False,
    hovertemplate="%{x}: %{text} of window net<extra></extra>",
))
g_fig.update_layout(title="Net sales share by governorate")
theme.apply_plotly_style(g_fig)
g_fig.update_layout(showlegend=False)
g_fig.update_yaxes(tickformat=".0%")

with b_col:
    st.plotly_chart(b_fig, width="stretch", config={"displayModeBar": False})
with g_col:
    st.plotly_chart(g_fig, width="stretch", config={"displayModeBar": False})

# ------------------------------------------------------------- mix (T043) --
cat = data.q(
    """
    SELECT category_en AS category, SUM(net_sales) AS net
    FROM views.sales_enriched WHERE order_date BETWEEN ? AND ?
    GROUP BY 1 ORDER BY 2 DESC
    """,
    (start, end),
)
chan = data.q(
    """
    SELECT sales_channel AS channel, SUM(net_sales) AS net
    FROM views.sales_enriched WHERE order_date BETWEEN ? AND ?
    GROUP BY 1 ORDER BY 2 DESC
    """,
    (start, end),
)

c_col, ch_col = st.columns(2)
c_fig = go.Figure(go.Pie(
    hole=0.56, labels=cat.category, values=cat.net,
    marker={"colors": theme.COLORS}, textinfo="percent",
    hovertemplate="%{label}: EGP %{value:,.0f} (%{percent})<extra></extra>",
))
c_fig.update_layout(title="Category mix (net sales)")
theme.apply_plotly_style(c_fig)

ch_fig = go.Figure(go.Pie(
    hole=0.56, labels=chan.channel, values=chan.net,
    marker={"colors": theme.COLORS}, textinfo="label+percent",
    hovertemplate="%{label}: EGP %{value:,.0f} (%{percent})<extra></extra>",
))
ch_fig.update_layout(title="Channel mix (net sales)")
theme.apply_plotly_style(ch_fig)

with c_col:
    st.plotly_chart(c_fig, width="stretch", config={"displayModeBar": False})
with ch_col:
    st.plotly_chart(ch_fig, width="stretch", config={"displayModeBar": False})

# ------------------------------------------------------- data notes (T044) --
lines_in_window = data.scalar(
    "SELECT COUNT(*) FROM views.sales_enriched WHERE order_date BETWEEN ? AND ?",
    (start, end),
)
guest_orders = data.scalar(
    """
    SELECT COUNT(DISTINCT sales_order_id) FROM views.sales_enriched
    WHERE customer_id IS NULL AND order_date BETWEEN ? AND ?
    """,
    (start, end),
)

with st.expander("Data notes - definitions & caveats for this page", expanded=False):
    st.markdown(
        f"""
- **Source rows**: {int(lines_in_window):,} sales-order lines in the selected window
  (`views.sales_enriched` = item lines × orders × product × branch, guest-safe).
- **Net sales** = Σ `net_line_EGP` after per-line discounts, before the flat 14% VAT.
- **Gross profit** = Σ `margin_EGP` as recorded per line (no COGS reconstruction).
- **Orders** = distinct order heads (`COUNT(DISTINCT sales_order_id)`).
- **Active customers** = distinct logged-in buyers; guest orders ({int(guest_orders):,} in
  window, A4) are excluded by definition but fully counted in revenue metrics.
- **Return rate** = orders placed in the window with ≥1 recorded return. Returns are
  capped at their line value in views (`refund_capped`, A3); counted at order level here.
- **YoY deltas** compare *the same calendar-span one year earlier* — e.g. a partial
  current year (data ends {DATA_END.isoformat()}) is compared to the same months of the
  prior year, per audit policy A5. All-time mode has no comparison window.
- **Known data quirks**: purchase-order magnitudes are absolute-only (A1); marketing
  attribution is rebuilt from real orders (A2); see `docs/DATA_AUDIT.md` for the full A1-A10 list.
"""
    )

# ------------------------- platform data notes (folded from the old Home) ----
st.caption(
    "25 source tables · 26 curated views · 16 dashboards · monthly snapshots from "
    f"Oct 2018 to {DATA_END.isoformat()} · all figures in EGP."
)

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
