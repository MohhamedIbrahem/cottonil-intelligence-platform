"""Price & Promotion Intelligence (S13).

Discounts exist at line level; there are no promotion IDs, competitor prices or
cost shocks. The elasticity model uses SKU and month fixed effects and reports
the result honestly: the current data show no usable price response.
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import plotly.graph_objects as go
import streamlit as st

from app import analytics, data, theme
from app.filters import DATA_END, render_period_selector

st.set_page_config(
    page_title="Price & Promotion · Cottonil",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.apply_theme()

start, end, label, _ = render_period_selector()
ym_start, ym_end = start.strftime("%Y-%m"), end.strftime("%Y-%m")


@st.cache_data(ttl=600, show_spinner="Estimating price response…")
def _elasticity() -> tuple:
    frame = data.q(
        """
        SELECT sku_id, ym, units, avg_unit_price, discount_rate, category_en
        FROM views.sku_monthly
        """
    )
    overall = analytics.price_elasticity(frame)
    by_category = analytics.price_elasticity(frame, group_col="category_en")
    return overall, by_category


period = data.q(
    """
    SELECT SUM(gross_sales) AS gross_sales,
           SUM(discount) AS discount,
           SUM(net_sales) AS net_sales,
           SUM(gross_profit) AS gross_profit,
           SUM(net_sales) FILTER (WHERE discount > 0) AS discounted_net,
           COUNT(*) AS sku_months,
           COUNT(*) FILTER (WHERE discount > 0) AS discounted_sku_months
    FROM views.sku_monthly
    WHERE ym BETWEEN ? AND ?
    """,
    (ym_start, ym_end),
).iloc[0]

gross_sales = float(period.gross_sales or 0.0)
discount = float(period.discount or 0.0)
net_sales = float(period.net_sales or 0.0)
gross_profit = float(period.gross_profit or 0.0)
discount_rate = discount / gross_sales if gross_sales else 0.0
margin = gross_profit / net_sales if net_sales else 0.0
discounted_net_share = float(period.discounted_net or 0.0) / net_sales if net_sales else 0.0
discounted_sku_share = (
    float(period.discounted_sku_months) / float(period.sku_months)
    if float(period.sku_months)
    else 0.0
)

overall, by_category = _elasticity()
overall_row = overall.iloc[0]
beta = float(overall_row.beta_price)
beta_se = float(overall_row.se_price)
beta_p = float(overall_row.p_price)
within_r2 = float(overall_row.r2_within)
mean_discount = float(overall_row.mean_discount)
mean_price_move = float(overall_row.mean_abs_price_change)

theme.page_header(
    "Price & Promotion Intelligence",
    f"Reporting period: **{label}** · line-level discounts from `views.sku_monthly` · "
    f"no promotion IDs, competitor prices or cost shocks · data through {DATA_END.isoformat()}",
    eyebrow="Growth",
    badges=(('Failed price signal', 'warn'),),
)

cards = st.columns(4)
with cards[0]:
    theme.kpi_card(
        "Weighted discount rate",
        f"{discount_rate:.1%}",
        sub=f"{discounted_net_share:.0%} of net sales carried a discount",
    )
with cards[1]:
    theme.kpi_card(
        "Gross margin",
        f"{margin:.1%}",
        sub="recorded unit cost · excludes operating expenses",
    )
with cards[2]:
    theme.kpi_card(
        "Discounted SKU-months",
        f"{discounted_sku_share:.0%}",
        sub=f"{int(period.discounted_sku_months):,} of {int(period.sku_months):,} rows in the window",
    )
with cards[3]:
    theme.kpi_card(
        "Price response β",
        f"{beta:+.2f}",
        sub=f"SE {beta_se:.2f} · within-R² {within_r2:.4f} · all-history model",
    )

if beta >= 0 or within_r2 < 0.01:
    st.warning(
        "No usable price-elasticity signal. The within-SKU/month log-price "
        f"coefficient is **{beta:+.3f}** (SE {beta_se:.3f}, p={beta_p:.3f}), the "
        "wrong sign for demand, and the fixed-effects model explains essentially "
        f"none of the variation (within-R² {within_r2:.4f}). Discounts average "
        f"{mean_discount:.1%} and are nearly universal; within-SKU monthly price "
        f"moves average {mean_price_move:.1%}. Treat this as a diagnostic, not a "
        "pricing tool."
    )

st.divider()

# ------------------------------------------------------- category price/margin --
category = data.q(
    """
    SELECT category_en,
           SUM(discount) / NULLIF(SUM(gross_sales), 0)     AS discount_rate,
           SUM(gross_profit) / NULLIF(SUM(net_sales), 0)   AS gross_margin,
           SUM(net_sales)                                  AS net_sales,
           SUM(units)                                      AS units
    FROM views.sku_monthly
    WHERE ym BETWEEN ? AND ?
    GROUP BY 1
    ORDER BY net_sales DESC
    """,
    (ym_start, ym_end),
)

left, right = st.columns((3, 2))
with left:
    bubble = go.Figure(
        go.Scatter(
            x=category["discount_rate"],
            y=category["gross_margin"],
            mode="markers",
            text=category["category_en"],
            marker={
                "size": category["net_sales"] / category["net_sales"].max() * 42 + 12,
                "color": theme.ACCENT,
                "opacity": 0.72,
                "line": {"color": theme.CARD, "width": 1},
            },
            customdata=category[["net_sales", "units"]],
            hovertemplate=(
                "%{text}<br>Discount %{x:.1%}<br>Margin %{y:.1%}"
                "<br>Net EGP %{customdata[0]:,.0f}<extra></extra>"
            ),
        )
    )
    bubble.update_layout(
        title="Category discount depth vs gross margin",
        xaxis_title="Weighted discount rate",
        yaxis_title="Gross margin",
        xaxis_tickformat=".1%",
        yaxis_tickformat=".1%",
        showlegend=False,
    )
    theme.apply_plotly_style(bubble)
    st.plotly_chart(bubble, width="stretch", config={"displayModeBar": False})
    st.caption(
        "Hover a bubble for the category, net sales and units. Bubble size = net "
        "sales in the window; category averages hide SKU-level variation."
    )

with right:
    depth = data.q(
        """
        SELECT discount_rate, net_sales
        FROM views.sku_monthly
        WHERE ym BETWEEN ? AND ?
        """,
        (ym_start, ym_end),
    )
    hist = go.Figure(
        go.Histogram(
            x=depth["discount_rate"],
            nbinsx=40,
            marker_color=theme.ACCENT_2,
            hovertemplate="Discount %{x:.0%}<br>SKU-months %{y}<extra></extra>",
        )
    )
    hist.add_vline(
        x=discount_rate,
        line={"color": theme.BAD, "width": 2, "dash": "dash"},
        annotation_text=f"weighted {discount_rate:.1%}",
        annotation_position="top right",
    )
    hist.update_layout(
        title="Discount-depth distribution",
        xaxis_title="Discount rate",
        yaxis_title="SKU-months",
        xaxis_tickformat=".0%",
        showlegend=False,
    )
    theme.apply_plotly_style(hist)
    hist.update_xaxes(range=[0, float(depth.discount_rate.max()) * 1.06])
    st.plotly_chart(hist, width="stretch", config={"displayModeBar": False})
    st.caption("Discounts are shallow and tightly clustered; there is no deep-promotion tail.")

st.divider()

# ------------------------------------------------------- price/margin over time --
monthly = data.q(
    """
    SELECT ym,
           SUM(discount) / NULLIF(SUM(gross_sales), 0)     AS discount_rate,
           SUM(gross_profit) / NULLIF(SUM(net_sales), 0)   AS gross_margin,
           SUM(net_sales)                                  AS net_sales
    FROM views.sku_monthly
    WHERE ym BETWEEN ? AND ?
    GROUP BY 1
    ORDER BY 1
    """,
    (ym_start, ym_end),
)
trend = go.Figure()
trend.add_trace(
    go.Scatter(
        x=monthly.ym,
        y=monthly.discount_rate,
        name="Discount rate",
        mode="lines+markers",
        line={"color": theme.ACCENT, "width": 2},
    )
)
trend.add_trace(
    go.Scatter(
        x=monthly.ym,
        y=monthly.gross_margin,
        name="Gross margin",
        mode="lines+markers",
        yaxis="y2",
        line={"color": theme.GOOD, "width": 2},
    )
)
trend.update_layout(
    title="Discount rate and gross margin by month",
    yaxis={"title": "Discount rate", "tickformat": ".1%", "dtick": 0.001},
    yaxis2={
        "title": "Gross margin",
        "tickformat": ".1%",
        "dtick": 0.001,
        "overlaying": "y",
        "side": "right",
        "showgrid": False,
    },
    hovermode="x unified",
)
theme.apply_plotly_style(trend)
st.plotly_chart(trend, width="stretch", config={"displayModeBar": False})

st.divider()

# ---------------------------------------------------------- elasticity table ----
theme.section_header("Price-response estimates by category")
st.caption(
    "Within-SKU and within-month fixed effects; log units on log net price and "
    "discount rate; SKU-clustered standard errors. Positive coefficients are "
    "implausible for demand. Category estimates are not multiple-testing corrected."
)
category_el = by_category[by_category["group"] != "All"].copy()
category_el["verdict"] = [
    (
        "No signal"
        if (p >= 0.05 or r2 < 0.01)
        else ("Negative & significant" if b < 0 else "Positive & significant (wrong sign)")
    )
    for b, p, r2 in zip(
        category_el.beta_price,
        category_el.p_price,
        category_el.r2_within,
        strict=True,
    )
]
category_el = category_el.sort_values("n_obs", ascending=False)
st.dataframe(
    category_el[
        ["group", "n_obs", "n_skus", "beta_price", "se_price", "p_price", "r2_within", "verdict"]
    ].rename(
        columns={
            "group": "Category",
            "n_obs": "SKU-months",
            "n_skus": "SKUs",
            "beta_price": "β price",
            "se_price": "SE",
            "p_price": "p-value",
            "r2_within": "Within-R²",
            "verdict": "Verdict",
        }
    ),
    hide_index=True,
    column_config={
        "Category": st.column_config.TextColumn("Category"),
        "SKU-months": st.column_config.NumberColumn("SKU-months", format="%.0f"),
        "SKUs": st.column_config.NumberColumn("SKUs", format="%.0f"),
        "β price": st.column_config.NumberColumn("β price", format="%.3f"),
        "SE": st.column_config.NumberColumn("SE", format="%.3f"),
        "p-value": st.column_config.NumberColumn("p-value", format="%.3f"),
        "Within-R²": st.column_config.NumberColumn("Within-R²", format="%.4f"),
        "Verdict": st.column_config.TextColumn("Verdict"),
    },
)

# ------------------------------------------------------ most discounted rows ---
discounted = data.q(
    """
    SELECT ym, product_name_ar, category_en, size, color_ar,
           units, net_sales, discount_rate, gross_margin
    FROM views.sku_monthly
    WHERE ym BETWEEN ? AND ? AND discount_rate > 0
    ORDER BY discount_rate DESC, net_sales DESC
    LIMIT 20
    """,
    (ym_start, ym_end),
)
discounted["discount_rate"] *= 100
discounted["gross_margin"] *= 100
theme.section_header("Deepest discounts in the window")
st.dataframe(
    discounted,
    hide_index=True,
    column_config={
        "ym": st.column_config.TextColumn("Month", width="small"),
        "product_name_ar": st.column_config.TextColumn("Product"),
        "category_en": st.column_config.TextColumn("Category"),
        "size": st.column_config.TextColumn("Size", width="small"),
        "color_ar": st.column_config.TextColumn("Color", width="small"),
        "units": st.column_config.NumberColumn("Units", format="%.0f"),
        "net_sales": st.column_config.NumberColumn("Net (EGP)", format="%.0f"),
        "discount_rate": st.column_config.NumberColumn("Discount (%)", format="%.1f"),
        "gross_margin": st.column_config.NumberColumn("Margin (%)", format="%.1f"),
    },
)

with st.expander("What this page can and cannot say (audit A11)", expanded=False):
    st.markdown(
        "- **Real fields**: `views.sku_monthly` carries line-level gross, discount, "
        "net and recorded unit cost. Discount rate = discount / gross; margin = "
        "gross profit / net.\n"
        "- **No promotion table**: there are no promo IDs, campaign flags, coupons, "
        "competitor prices, or cost-change dates. A discount is inferred from the "
        "line, not from a promotion calendar.\n"
        "- **Elasticity model**: log units on log net price plus discount rate, with "
        "SKU and month fixed effects. Net price already reflects the discount, so "
        "the two regressors are correlated; the joint result is reported for "
        "completeness, not as a causal effect.\n"
        "- **Result**: the coefficient is positive and tiny in explanatory power. "
        "That is a failed signal, not evidence that demand rises with price. The "
        "dataset's discounts are shallow (~4%) and nearly uniform, leaving little "
        "price variation to identify a response.\n"
        "- **Do not** use these estimates to set prices, forecast promo lift, or "
        "claim promotion ROI."
    )
