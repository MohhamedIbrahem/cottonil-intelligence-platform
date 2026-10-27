"""Product Profitability & Margin (S16).

Product-level all-time margins are almost uniform, so the useful variation is
SKU-month margin. The 30% low-margin flag is a documented display threshold, not
a business rule. Margin uses recorded unit cost and excludes operating expenses.
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import plotly.graph_objects as go
import streamlit as st

from app import data, theme
from app.filters import DATA_END, selected_period

start, end, label, _ = selected_period()
ym_start, ym_end = start.strftime("%Y-%m"), end.strftime("%Y-%m")

LOW_MARGIN = 0.30

period = data.q(
    """
    SELECT SUM(net_sales)                                        AS net_sales,
           SUM(gross_profit)                                     AS gross_profit,
           SUM(units)                                            AS units,
           COUNT(*)                                              AS sku_months,
           COUNT(*) FILTER (WHERE gross_margin < ?)              AS low_margin_sku_months,
           SUM(net_sales) FILTER (WHERE gross_margin < ?)        AS low_margin_net
    FROM views.sku_monthly
    WHERE ym BETWEEN ? AND ?
    """,
    (LOW_MARGIN, LOW_MARGIN, ym_start, ym_end),
).iloc[0]

net_sales = float(period.net_sales or 0.0)
gross_profit = float(period.gross_profit or 0.0)
margin = gross_profit / net_sales if net_sales else 0.0
low_margin_net = float(period.low_margin_net or 0.0)
low_margin_share = low_margin_net / net_sales if net_sales else 0.0
low_row_share = (
    float(period.low_margin_sku_months) / float(period.sku_months)
    if float(period.sku_months)
    else 0.0
)

category = data.q(
    """
    SELECT category_en,
           SUM(net_sales)                                      AS net_sales,
           SUM(gross_profit)                                   AS gross_profit,
           SUM(gross_profit) / NULLIF(SUM(net_sales), 0)       AS gross_margin,
           SUM(units)                                          AS units,
           COUNT(DISTINCT sku_id)                              AS skus,
           SUM(net_sales) FILTER (WHERE gross_margin < ?)      AS low_margin_net
    FROM views.sku_monthly
    WHERE ym BETWEEN ? AND ?
    GROUP BY 1
    ORDER BY gross_margin
    """,
    (LOW_MARGIN, ym_start, ym_end),
)
category["low_margin_share"] = category.low_margin_net / category.net_sales

sku_months = data.q(
    """
    SELECT gross_margin, net_sales
    FROM views.sku_monthly
    WHERE ym BETWEEN ? AND ?
    """,
    (ym_start, ym_end),
)

products = data.q(
    """
    SELECT product_name_ar, category_en, audience,
           SUM(net_sales)                                      AS net_sales,
           SUM(gross_profit)                                   AS gross_profit,
           SUM(gross_profit) / NULLIF(SUM(net_sales), 0)       AS gross_margin,
           SUM(units)                                          AS units,
           SUM(discount) / NULLIF(SUM(gross_sales), 0)         AS discount_rate
    FROM views.product_monthly
    WHERE ym BETWEEN ? AND ?
    GROUP BY product_id, product_name_ar, category_en, audience
    ORDER BY gross_profit DESC
    LIMIT 20
    """,
    (ym_start, ym_end),
)

alerts = data.q(
    """
    SELECT ym, sku_id, product_name_ar, category_en, size, color_ar,
           units, net_sales, discount_rate, gross_margin
    FROM views.sku_monthly
    WHERE ym BETWEEN ? AND ? AND gross_margin < ?
    ORDER BY net_sales DESC
    LIMIT 25
    """,
    (ym_start, ym_end, LOW_MARGIN),
)

theme.page_header(
    "Product Profitability & Margin",
    f"Reporting period: **{label}** · SKU-month margin from `views.sku_monthly` · "
    f"low-margin flag = gross margin below **{LOW_MARGIN:.0%}** (display policy) · "
    f"data through {DATA_END.isoformat()}",
    eyebrow="Growth",
    badges=('Display threshold',),
)

cards = st.columns(4)
with cards[0]:
    theme.kpi_card(
        "Net sales",
        theme.fmt_egp(net_sales),
        sub=f"{theme.fmt_int(float(period.units or 0))} units · {int(period.sku_months):,} SKU-months",
        tone="blue",
    )
with cards[1]:
    theme.kpi_card(
        "Gross profit",
        theme.fmt_egp(gross_profit),
        sub="recorded unit cost · excludes operating expenses",
        tone="green",
    )
with cards[2]:
    theme.kpi_card(
        "Gross margin",
        f"{margin:.1%}",
        sub="weighted across all SKU-months in the window",
        tone="teal",
    )
with cards[3]:
    theme.kpi_card(
        "Low-margin net exposure",
        f"{low_margin_share:.1%}",
        sub=f"{low_row_share:.1%} of SKU-months sit below {LOW_MARGIN:.0%}",
        tone="red",
    )

# Insights-first strip (App Shell v3): from the window aggregates above.
theme.insight_strip([
    {
        "icon": "\U0001F4B9", "label": "Gross margin",
        "value": f"{margin:.1%}",
        "sub": f"{theme.fmt_egp(gross_profit)} gross profit on {theme.fmt_egp(net_sales)} net",
        "tone": "good" if margin >= 0.3 else "warn",
    },
    {
        "icon": "\u26A0\uFE0F", "label": "Low-margin exposure",
        "value": f"{low_margin_share:.1%} of net sales",
        "sub": f"from SKU-months below the {LOW_MARGIN:.0%} margin flag",
        "tone": "bad" if low_margin_share >= 0.25 else "warn",
    },
    {
        "icon": "\U0001F4E6", "label": "Assortment breadth",
        "value": f"{int(period.sku_months):,} SKU-months",
        "sub": f"{theme.fmt_int(float(period.units or 0))} units sold in the window",
        "tone": "neutral",
    },
])

st.divider()

left, right = st.columns((3, 2))

with left:
    cat_fig = go.Figure(
        go.Bar(
            x=category.gross_margin,
            y=category.category_en,
            orientation="h",
            marker_color=[
                theme.BAD if value < LOW_MARGIN else theme.ACCENT
                for value in category.gross_margin
            ],
            customdata=category[["net_sales", "low_margin_share"]],
            text=[f"{value:.1%}" for value in category.gross_margin],
            textposition="outside",
            hovertemplate=(
                "%{y}<br>Margin %{x:.1%}<br>Net EGP %{customdata[0]:,.0f}"
                "<br>Low-margin net share %{customdata[1]:.1%}<extra></extra>"
            ),
        )
    )
    cat_fig.add_vline(
        x=LOW_MARGIN,
        line={"color": theme.BAD, "width": 1, "dash": "dash"},
        annotation_text=f"{LOW_MARGIN:.0%} flag",
        annotation_position="top",
    )
    cat_fig.update_layout(
        title="Category gross margin",
        xaxis={"title": "Gross margin", "tickformat": ".0%", "range": [0, 0.46]},
        yaxis_title="",
        showlegend=False,
    )
    theme.apply_plotly_style(cat_fig)
    st.plotly_chart(cat_fig, width="stretch", config={"displayModeBar": False})
    st.caption(
        "Category averages are tightly clustered around 38%; the low-margin tail "
        "is a SKU-month phenomenon, not a category-level one."
    )

with right:
    median_margin = float(sku_months.gross_margin.median())
    dist = go.Figure(
        go.Histogram(
            x=sku_months.gross_margin,
            nbinsx=50,
            marker_color=theme.ACCENT_2,
            hovertemplate="Margin %{x:.0%}<br>SKU-months %{y}<extra></extra>",
        )
    )
    dist.add_vline(
        x=LOW_MARGIN,
        line={"color": theme.BAD, "width": 2, "dash": "dash"},
        annotation_text=f"{LOW_MARGIN:.0%} flag",
        annotation_position="top left",
    )
    dist.add_vline(
        x=median_margin,
        line={"color": theme.TEXT_MUTED, "width": 1, "dash": "dot"},
        annotation_text=f"median {median_margin:.1%}",
        annotation_position="top right",
    )
    dist.update_layout(
        title="SKU-month margin distribution",
        xaxis={"title": "Gross margin", "tickformat": ".0%"},
        yaxis_title="SKU-months",
        showlegend=False,
    )
    theme.apply_plotly_style(dist)
    st.plotly_chart(dist, width="stretch", config={"displayModeBar": False})
    st.caption(
        f"Median SKU-month margin {median_margin:.1%}; the range runs from "
        f"{sku_months.gross_margin.min():.1%} to {sku_months.gross_margin.max():.1%}."
    )

st.divider()

# --------------------------------------------------------- category summary -----
category_table = category.copy()
for column in ("gross_margin", "low_margin_share"):
    category_table[column] *= 100
theme.section_header("Category summary")
st.dataframe(
    category_table[
        ["category_en", "skus", "units", "net_sales", "gross_profit", "gross_margin", "low_margin_share"]
    ],
    hide_index=True,
    column_config={
        "category_en": st.column_config.TextColumn("Category"),
        "skus": st.column_config.NumberColumn("SKUs", format="%.0f"),
        "units": st.column_config.NumberColumn("Units", format="%.0f"),
        "net_sales": st.column_config.NumberColumn("Net sales (EGP)", format="%.0f"),
        "gross_profit": st.column_config.NumberColumn("Gross profit (EGP)", format="%.0f"),
        "gross_margin": st.column_config.NumberColumn("Margin (%)", format="%.1f"),
        "low_margin_share": st.column_config.NumberColumn("Low-margin net share (%)", format="%.1f"),
    },
)
st.caption(
    "None in the low-margin column means no SKU-month in that category fell "
    "below the 30% display threshold."
)

# ---------------------------------------------------------- top products -------
product_table = products.copy()
product_table["gross_margin"] *= 100
product_table["discount_rate"] *= 100
theme.section_header("Top-20 products by gross profit")
st.dataframe(
    product_table,
    hide_index=True,
    column_config={
        "product_name_ar": st.column_config.TextColumn("Product"),
        "category_en": st.column_config.TextColumn("Category"),
        "audience": st.column_config.TextColumn("Audience", width="small"),
        "net_sales": st.column_config.NumberColumn("Net sales (EGP)", format="%.0f"),
        "gross_profit": st.column_config.NumberColumn("Gross profit (EGP)", format="%.0f"),
        "gross_margin": st.column_config.NumberColumn("Margin (%)", format="%.1f"),
        "units": st.column_config.NumberColumn("Units", format="%.0f"),
        "discount_rate": st.column_config.NumberColumn("Discount (%)", format="%.1f"),
    },
)

# ------------------------------------------------------- low-margin alerts -----
alert_table = alerts.copy()
alert_table["discount_rate"] *= 100
alert_table["gross_margin"] *= 100
theme.section_header(f"Low-margin SKU-month alerts — below {LOW_MARGIN:.0%} (top 25 by net sales)")
if alert_table.empty:
    st.info("No SKU-months below the display threshold in this window.")
else:
    st.dataframe(
        alert_table,
        hide_index=True,
        column_config={
            "ym": st.column_config.TextColumn("Month", width="small"),
            "sku_id": st.column_config.TextColumn("SKU", width="small"),
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
    st.caption(
        "Sorted by net sales, not by margin: a low-margin row matters most when it "
        "is large. The flag is a review trigger, not proof of a pricing error."
    )

with st.expander("Why SKU-month margin, and what the flag means (audit A13)", expanded=False):
    st.markdown(
        "- **Grain**: product-level all-time margins are almost uniform "
        "(37.5–39.4% across 139 products), so ranking products by margin is "
        "uninformative. SKU-month margins range from roughly 7.5% to 56%, which "
        "is where the real variation lives.\n"
        "- **Margin** = recorded gross profit / net sales. Net sales is after "
        "line discounts and before 14% VAT; gross profit uses the recorded "
        "`unit_cost_EGP`, so it excludes operating expenses, markdowns after the "
        "sale, shrinkage and freight.\n"
        f"- **{LOW_MARGIN:.0%} flag**: a display threshold chosen after profiling "
        "the SKU-month distribution. It is not a contractual margin floor or a "
        "company policy. A row below it is a review candidate, not a loss.\n"
        "- **No cost history or promo calendar**: unit cost is recorded per line; "
        "there is no separate cost-change or promotion table to attribute a "
        "margin move to a specific cause.\n"
        "- **Guest orders** are included in sales/margin (they are real revenue) "
        "but not in customer-level views (audit A4)."
    )
