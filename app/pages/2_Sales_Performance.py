"""Sales Performance (deck p.3) - category-filterable sales deep dive.

US3 / tasks T050-T054. Same period selector as every page; adds a category
filter that scopes every chart on the page. All numbers from views.* (read-only).
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))  # pages/ -> app/ -> repo root

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import data, theme
from app.filters import DATA_END, previous_period, render_period_selector

st.set_page_config(
    page_title="Sales Performance · Cottonil",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.apply_theme()

start, end, label, mode = render_period_selector()

# ------------------------------------------------------------ category scope --
_all_cats = "All categories"
categories = data.q(
    "SELECT DISTINCT category_en FROM views.sales_enriched ORDER BY 1"
).category_en.tolist()
category = st.sidebar.selectbox("Category", [_all_cats, *categories], index=0)
cat_where = "" if category == _all_cats else " AND category_en = ?"

if not st.session_state.get("_sales_toast_shown"):
    st.toast(f"Sales scope: {category}", icon="💰")
    st.session_state["_sales_toast_shown"] = True

st.title("💰 Sales Performance")
st.caption(
    f"Reporting period: **{label}** · category scope: **{category}** · "
    f"guests included in revenue (A4) · EGP excl. 14% VAT · data through {DATA_END.isoformat()}"
)

params = (start, end) if category == _all_cats else (start, end, category)

# --------------------------------------------------------- headline (T052) --
def _sales_kpis(window: tuple) -> pd.Series:  # type: ignore[type-arg]
    s, e = window
    base = (
        "SELECT SUM(net_sales) AS net, SUM(quantity) AS units, "
        "COUNT(DISTINCT sales_order_id) AS orders FROM views.sales_enriched "
        "WHERE order_date BETWEEN ? AND ?"
    )
    return data.q(base + cat_where, (s, e) + ((category,) if category != _all_cats else ())).iloc[0]


cur = _sales_kpis((start, end))
prev_window = previous_period(start, end, mode)
prior = _sales_kpis(prev_window) if prev_window else None
prev_label = (
    f"{prev_window[0].strftime('%b %Y')} \u2013 {prev_window[1].strftime('%b %Y')}"
    if prev_window else "no window"
)


def _delta(current: float, previous: float | None) -> tuple[str, bool, bool]:
    """(delta_text, arrow_up, good_bad) - on this page every metric is 'up is good'."""
    if previous is None or pd.isna(previous) or previous == 0:
        return "n/a", True, False
    pct = float(current) / float(previous) - 1.0
    up = pct >= 0
    return f"{pct:+.1%} vs {prev_label}", up, up


aov_cur = float(cur.net) / max(float(cur.orders), 1)
aov_prev = None if prior is None else float(prior.net) / max(float(prior.orders), 1)
items_order_cur = float(cur.units) / max(float(cur.orders), 1)
items_order_prev = None if prior is None else float(prior.units) / max(float(prior.orders), 1)

k_cards = [
    ("Net sales", theme.fmt_egp(float(cur.net)),
     _delta(cur.net, None if prior is None else prior.net), "line net after discounts"),
    ("Orders", theme.fmt_int(float(cur.orders)),
     _delta(cur.orders, None if prior is None else prior.orders), "distinct order heads"),
    ("Avg order value", theme.fmt_egp(aov_cur),
     _delta(aov_cur, aov_prev), "net / orders"),
    ("Items per order", f"{items_order_cur:,.2f}",
     _delta(items_order_cur, items_order_prev), "units / orders"),
    ("Units sold", theme.fmt_int(float(cur.units)),
     _delta(cur.units, None if prior is None else prior.units), "pieces across lines"),
]
cols = st.columns(5)
for col, (title, value, delta, sub) in zip(cols, k_cards, strict=True):
    with col:
        theme.kpi_card(title, value, delta=delta[0], delta_up=delta[1], delta_good=delta[2], sub=sub)

st.divider()

# -------------------------------------------------- monthly trend (T050) --
trend = data.q(
    """
    SELECT ym, SUM(net_sales) AS net, SUM(gross_profit) AS gross_profit
    FROM views.sales_enriched
    WHERE order_date BETWEEN ? AND ?
    """
    + cat_where + " GROUP BY ym ORDER BY ym",
    params + (),
).dropna(subset=["net"])
trend["month"] = pd.to_datetime(trend.ym + "-01")

trend_fig = go.Figure()
trend_fig.add_trace(go.Scatter(
    x=trend.month, y=trend.net, name="Net sales",
    mode="lines+markers", line={"width": 3, "color": theme.ACCENT_2},
    fill="tozeroy", fillcolor="rgba(2,132,199,0.10)",
    hovertemplate="%{x|%b %Y}: EGP %{y:,.0f}<extra></extra>",
))
trend_fig.add_trace(go.Scatter(
    x=trend.month, y=trend.gross_profit, name="Gross profit",
    mode="lines+markers", line={"width": 2, "color": theme.WARN},
    hovertemplate="%{x|%b %Y}: EGP %{y:,.0f}<extra></extra>",
))
trend_fig.update_layout(title=f"Monthly net sales & gross profit — {category}")
theme.apply_plotly_style(trend_fig)
trend_fig.update_xaxes(tickformat="%b %Y")
st.plotly_chart(trend_fig, width="stretch", config={"displayModeBar": False})

# ------------------------------------------ top products table (T051) --
top_products = data.q(
    """
    SELECT product_name_ar AS product, category_en AS category,
           SUM(quantity) AS units, SUM(net_sales) AS net_sales,
           COUNT(DISTINCT sales_order_id) AS orders,
           SUM(gross_profit) AS gross_profit
    FROM views.sales_enriched
    WHERE order_date BETWEEN ? AND ?
    """
    + cat_where
    + " GROUP BY 1, 2 ORDER BY net_sales DESC",
    params,
)
top_products = top_products.head(15)

st.markdown("#### Top products in this window")
st.dataframe(
    top_products,
    hide_index=True,
    column_config={
        "product": st.column_config.TextColumn("Product"),
        "category": st.column_config.TextColumn("Category", width="small"),
        "units": st.column_config.NumberColumn("Units", format="%d"),
        "net_sales": st.column_config.NumberColumn("Net sales (EGP)", format="%.0f"),
        "orders": st.column_config.NumberColumn("Orders", format="%d"),
        "gross_profit": st.column_config.NumberColumn("Gross profit (EGP)", format="%.0f"),
    },
)

# ------------------------------------- category / audience mix donuts (T052) --
donut_col1, donut_col2 = st.columns(2)
if category == _all_cats:
    cat_mix = data.q(
        """
        SELECT COALESCE(category_en, 'Unknown') AS name, SUM(net_sales) AS net
        FROM views.sales_enriched WHERE order_date BETWEEN ? AND ?
        GROUP BY 1 ORDER BY 2 DESC
        """,
        (start, end),
    )
    donut_title, donut_src = "Category mix (net)", cat_mix
else:
    aud_mix = data.q(
        """
        SELECT COALESCE(audience, 'Unspecified') AS name, SUM(net_sales) AS net
        FROM views.sales_enriched WHERE order_date BETWEEN ? AND ? AND category_en = ?
        GROUP BY 1 ORDER BY 2 DESC
        """,
        (start, end, category),
    )
    donut_title, donut_src = f"Audience mix — {category}", aud_mix

mix_fig = go.Figure(go.Pie(
    hole=0.56, labels=donut_src.name, values=donut_src.net,
    marker={"colors": theme.COLORS}, textinfo="percent",
    textfont={"color": theme.TEXT_ON_COLOR},
    hovertemplate="%{label}: EGP %{value:,.0f} (%{percent})<extra></extra>",
))
mix_fig.update_layout(title=donut_title)
theme.apply_plotly_style(mix_fig)

# -------------------------------------- governorate breakdown (T053) --
gov = data.q(
    """
    SELECT branch_governorate_ar AS governorate, SUM(net_sales) AS net,
           COUNT(DISTINCT sales_order_id) AS orders
    FROM views.sales_enriched
    WHERE order_date BETWEEN ? AND ?
    """
    + cat_where
    + " GROUP BY 1 ORDER BY 2 DESC",
    params,
)
gov["share"] = gov.net / gov.net.sum()

gov_fig = go.Figure(go.Bar(
    x=gov.governorate, y=gov.share,
    marker={"color": theme.ACCENT},
    text=[theme.fmt_pct(s) for s in gov.share], textposition="outside", cliponaxis=False,
    customdata=gov.net,
    hovertemplate="%{x}: %{text} of net (EGP %{customdata:,.0f})<extra></extra>",
))
gov_fig.update_layout(title=f"Net-share by governorate — {category}")
theme.apply_plotly_style(gov_fig)
gov_fig.update_yaxes(tickformat=".0%")

with donut_col1:
    st.plotly_chart(mix_fig, width="stretch", config={"displayModeBar": False})
with donut_col2:
    st.plotly_chart(gov_fig, width="stretch", config={"displayModeBar": False})

# -------------------------------------------------------- notes (T054) --
guest_orders = data.scalar(
    """
    SELECT COUNT(DISTINCT sales_order_id) FROM views.sales_enriched
    WHERE customer_id IS NULL AND order_date BETWEEN ? AND ?
    """
    + cat_where,
    params,
) or 0

with st.expander("Data notes - definitions & caveats for this page", expanded=False):
    st.markdown(
        f"""
- **Category filter** scopes *every* chart on this page; source is
  `products_catalog.category_en` carried through `views.sales_enriched`. Donut shows
  category mix in All mode, audience mix when a single category is selected.
- **Avg order value (AOV)** = Σ net line / distinct orders in window. Orders that
  contain several product lines are counted once, making AOV a *per-basket* figure.
- **Items per order** = Σ units / distinct orders (pieces per basket).
- **Top products table** ranks by net sales; units and order counts give the
  multiplicative context (a high-units/low-net product is a small-ticket item).
- **Guest checkout**: {int(guest_orders):,} guest orders in window ({theme.fmt_pct(
            float(guest_orders) / max(float(cur.orders), 1))}) — revenue fully
  counts them; customer-only metrics live on the Customers page (A4).
- **Unit-price caveat (A6)**: `unit_price_EGP` measures actual transacted prices;
  comparisons to catalog list prices are avoided without a note.
- **Data through {DATA_END.isoformat()}** — the current month is partial in every YoY.
"""
    )
