"""CLV & Churn (S19) - historical value and an honest churn test.

CLV is historical gross profit, not a forecast. Churn is defined as no purchase
for 365 days among customers with at least 365 days of tenure. The temporal
holdout is reported even though it fails: the available features do not separate
future repurchasers from non-repurchasers.
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from app import analytics, data, theme
from app.filters import DATA_END, render_period_selector

st.set_page_config(
    page_title="CLV & Churn · Cottonil",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.apply_theme()

render_period_selector()  # shared control; CLV/churn are profile facts, not window metrics

profile = data.q(
    """
    SELECT COUNT(*)                                              AS catalog_customers,
           COUNT(*) FILTER (WHERE has_purchased)                 AS buyers,
           SUM(gross_profit_lifetime)                            AS clv,
           MEDIAN(gross_profit_lifetime) FILTER (WHERE has_purchased) AS median_clv,
           COUNT(*) FILTER (WHERE is_churn_eligible)             AS eligible,
           COUNT(*) FILTER (WHERE churn_status = 'Churned')      AS churned,
           COUNT(*) FILTER (WHERE churn_status = 'Active')       AS active,
           COUNT(*) FILTER (WHERE churn_status = 'Never purchased') AS never_purchased,
           COUNT(*) FILTER (WHERE churn_status = 'Insufficient history') AS insufficient
    FROM views.customer_clv
""").iloc[0]

catalog = int(profile.catalog_customers)
buyers = int(profile.buyers)
eligible = int(profile.eligible)
churned = int(profile.churned)
churn_rate = churned / eligible if eligible else 0.0
buyer_share = buyers / catalog if catalog else 0.0

clv_values = data.q(
    "SELECT gross_profit_lifetime FROM views.customer_clv "
    "WHERE has_purchased ORDER BY gross_profit_lifetime"
).iloc[:, 0].to_numpy(dtype=float)
cumulative = np.cumsum(clv_values)
total_clv = float(cumulative[-1]) if len(cumulative) else 0.0
customer_share = np.insert(np.arange(1, len(clv_values) + 1) / len(clv_values), 0, 0.0)
clv_share = np.insert(cumulative / total_clv, 0, 0.0) if total_clv else customer_share
top_decile_share = 1 - float(clv_share[int(0.9 * len(clv_values))]) if len(clv_values) else 0.0

status = data.q(
    """
    SELECT churn_status, COUNT(*) AS customers
    FROM views.customer_clv
    GROUP BY 1
    ORDER BY customers DESC
    """
)
segment = data.q(
    """
    SELECT customer_segment,
           COUNT(*) FILTER (WHERE has_purchased)                 AS buyers,
           SUM(gross_profit_lifetime)                            AS clv,
           MEDIAN(gross_profit_lifetime) FILTER (WHERE has_purchased) AS median_clv
    FROM views.customer_clv
    GROUP BY 1
    ORDER BY clv DESC
    """
)
governorates = data.q(
    """
    SELECT governorate_ar,
           COUNT(*) FILTER (WHERE has_purchased)                 AS buyers,
           SUM(gross_profit_lifetime)                            AS clv,
           MEDIAN(gross_profit_lifetime) FILTER (WHERE has_purchased) AS median_clv
    FROM views.customer_clv
    WHERE has_purchased
    GROUP BY 1
    ORDER BY clv DESC
    LIMIT 10
    """
)

repurchase = data.q(
    """
    WITH base AS (
        SELECT customer_id,
               MAX(order_date) AS last_order,
               COUNT(DISTINCT sales_order_id) AS orders,
               date_diff('day', MAX(order_date), DATE '2025-10-18') AS recency
        FROM views.sales_enriched
        WHERE customer_id IS NOT NULL AND order_date < DATE '2025-10-18'
        GROUP BY 1
    ),
    labelled AS (
        SELECT b.*,
               CASE WHEN EXISTS (
                   SELECT 1 FROM views.sales_enriched v
                   WHERE v.customer_id = b.customer_id
                     AND v.order_date >= DATE '2025-10-18'
                     AND v.order_date < DATE '2026-10-18'
               ) THEN 1 ELSE 0 END AS repurchased
        FROM base b
    )
    SELECT CASE
               WHEN recency <= 30 THEN '0-30'
               WHEN recency <= 90 THEN '31-90'
               WHEN recency <= 180 THEN '91-180'
               WHEN recency <= 365 THEN '181-365'
               ELSE '365+'
           END AS recency_bucket,
           COUNT(*) AS customers,
           AVG(repurchased) AS repurchase_rate
    FROM labelled
    GROUP BY 1
    ORDER BY CASE recency_bucket
                 WHEN '0-30' THEN 1
                 WHEN '31-90' THEN 2
                 WHEN '91-180' THEN 3
                 WHEN '181-365' THEN 4
                 ELSE 5
             END
    """
)


def _feature_sql(cutoff: str) -> str:
    return f"""
    WITH orders AS (
        SELECT customer_id,
               COUNT(DISTINCT sales_order_id) AS orders,
               SUM(net_sales) AS monetary,
               MIN(order_date) AS first_order,
               MAX(order_date) AS last_order
        FROM views.sales_enriched
        WHERE customer_id IS NOT NULL AND order_date < DATE '{cutoff}'
        GROUP BY 1
    ),
    features AS (
        SELECT o.*,
               date_diff('day', last_order, DATE '{cutoff}') AS recency,
               date_diff('day', first_order, DATE '{cutoff}') AS tenure,
               monetary / NULLIF(orders, 0) AS aov
        FROM orders o
    )
    SELECT f.*, c.customer_segment,
           CASE WHEN EXISTS (
               SELECT 1 FROM views.sales_enriched v
               WHERE v.customer_id = f.customer_id
                 AND v.order_date >= DATE '{cutoff}'
                 AND v.order_date < DATE '{cutoff}' + INTERVAL 365 DAY
           ) THEN 1 ELSE 0 END AS bought_next
    FROM features f
    JOIN raw.customers c USING (customer_id)
    """


@st.cache_data(ttl=600, show_spinner="Running the churn holdout…")
def _churn() -> dict:
    train = data.q(_feature_sql("2024-10-18"))
    test = data.q(_feature_sql("2025-10-18"))
    result = analytics.churn_holdout(train, test)
    return {
        "auc": result["auc"],
        "accuracy": result["accuracy"],
        "base_churn": result["base_churn"],
        "predicted_churn": result["predicted_churn"],
        "n_train": result["n_train"],
        "n_test": result["n_test"],
        "coefficients": result["coefficients"],
        "deciles": result["deciles"],
    }


churn = _churn()

theme.page_header(
    "CLV & Churn",
    f"Profile facts as of **{DATA_END.isoformat()}** · historical CLV = lifetime gross "
    f"profit, not a forecast · churn = no purchase for 365 days with 365+ days tenure "
    f"· guests excluded (A4) · the sidebar period does not change this page",
    eyebrow="Advanced analytics",
    badges=('Historical CLV',),
)

cards = st.columns(4)
with cards[0]:
    theme.kpi_card(
        "Buyers",
        theme.fmt_int(float(buyers)),
        sub=f"{buyer_share:.1%} of {catalog:,} cataloged customers · rest never purchased",
    )
with cards[1]:
    theme.kpi_card(
        "Historical CLV",
        theme.fmt_egp(float(profile.clv)),
        sub="lifetime gross profit across identified buyers · excludes guests",
    )
with cards[2]:
    theme.kpi_card(
        "Median buyer CLV",
        theme.fmt_egp(float(profile.median_clv)),
        sub=f"top 10% of buyers hold {top_decile_share:.1%} of historical CLV",
    )
with cards[3]:
    theme.kpi_card(
        "Churn rate",
        f"{churn_rate:.1%}",
        sub=f"{churned:,} of {eligible:,} eligible buyers · 365+ days since last order",
    )

st.divider()

left, right = st.columns((3, 2))

with left:
    step = max(1, len(clv_values) // 250)
    lorenz = go.Figure()
    lorenz.add_trace(
        go.Scatter(
            x=customer_share[::step],
            y=clv_share[::step],
            mode="lines",
            name="Actual CLV concentration",
            line={"color": theme.ACCENT, "width": 2.5},
            hovertemplate="Cumulative customers %{x:.1%}<br>Cumulative CLV %{y:.1%}<extra></extra>",
        )
    )
    lorenz.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            name="Perfect equality",
            line={"color": theme.TEXT_MUTED, "width": 1, "dash": "dot"},
            hoverinfo="skip",
        )
    )
    lorenz.update_layout(
        title="Historical CLV concentration",
        xaxis={"title": "Cumulative share of buyers", "tickformat": ".0%"},
        yaxis={"title": "Cumulative share of CLV", "tickformat": ".0%"},
    )
    theme.apply_plotly_style(lorenz)
    st.plotly_chart(lorenz, width="stretch", config={"displayModeBar": False})
    st.caption(
        f"Top 10% of buyers account for {top_decile_share:.1%} of historical gross "
        "profit. CLV is skewed, so averages flatter the typical customer."
    )

with right:
    status_colors = {
        "Active": theme.GOOD,
        "Churned": theme.BAD,
        "Insufficient history": theme.WARN,
        "Never purchased": theme.NEUTRAL,
    }
    status_fig = go.Figure(
        go.Pie(
            hole=0.55,
            labels=status.churn_status,
            values=status.customers,
            marker={"colors": [status_colors.get(value, theme.ACCENT) for value in status.churn_status]},
            textinfo="percent",
            customdata=status.customers,
            hovertemplate="%{label}<br>%{customdata:,} customers (%{percent})<extra></extra>",
        )
    )
    status_fig.update_layout(title="Customer status")
    theme.apply_plotly_style(status_fig)
    st.plotly_chart(status_fig, width="stretch", config={"displayModeBar": False})
    st.caption(
        "Churned = 365+ days since last order and 365+ days tenure. Never-purchased "
        "and insufficient-history customers are not counted in the churn rate."
    )

st.divider()

left, right = st.columns(2)

with left:
    seg_fig = go.Figure(
        go.Bar(
            x=segment.customer_segment,
            y=segment.clv,
            marker_color=[theme.ACCENT, theme.ACCENT_2][: len(segment)],
            customdata=segment[["buyers", "median_clv"]],
            text=[f"{value:,.0f} buyers" for value in segment.buyers],
            textposition="outside",
            hovertemplate=(
                "%{x}<br>CLV EGP %{y:,.0f}<br>Buyers %{customdata[0]:,.0f}"
                "<br>Median CLV EGP %{customdata[1]:,.0f}<extra></extra>"
            ),
        )
    )
    seg_fig.update_layout(
        title="Historical CLV by customer segment",
        yaxis_title="Lifetime gross profit (EGP)",
        xaxis_title="",
        showlegend=False,
    )
    theme.apply_plotly_style(seg_fig)
    st.plotly_chart(seg_fig, width="stretch", config={"displayModeBar": False})

with right:
    overall_repurchase = float(
        (repurchase.customers * repurchase.repurchase_rate).sum() / repurchase.customers.sum()
    )
    rep_fig = go.Figure(
        go.Bar(
            x=repurchase.recency_bucket,
            y=repurchase.repurchase_rate,
            marker_color=theme.ACCENT_2,
            customdata=repurchase.customers,
            text=[f"{value:.1%}" for value in repurchase.repurchase_rate],
            textposition="inside",
            insidetextanchor="end",
            textfont={"color": theme.TEXT, "size": 11},
            hovertemplate="Recency %{x} days<br>Repurchase %{y:.1%}<br>Customers %{customdata:,}<extra></extra>",
        )
    )
    rep_fig.add_hline(
        y=overall_repurchase,
        line={"color": theme.TEXT_MUTED, "width": 1, "dash": "dot"},
        annotation_text=f"overall {overall_repurchase:.1%}",
        annotation_position="top right",
    )
    rep_fig.update_layout(
        title="12-month repurchase by recency at Oct 2025",
        xaxis_title="Days since last order at the cutoff",
        yaxis={"title": "Repurchase rate", "tickformat": ".0%"},
        showlegend=False,
    )
    theme.apply_plotly_style(rep_fig)
    st.plotly_chart(rep_fig, width="stretch", config={"displayModeBar": False})
    st.caption(
        "Repurchase is essentially flat across recency buckets — the behavioural "
        "signal a churn model would normally exploit is not present."
    )

st.divider()

# --------------------------------------------------------- churn holdout -------
theme.section_header("Churn holdout: can the available features predict lapse?")
st.caption(
    "Train on features at 2024-10-18 and labels in the following 12 months; test "
    "the same design at 2025-10-18. Only customers with 365+ days tenure are scored."
)

model_cards = st.columns(4)
with model_cards[0]:
    theme.kpi_card(
        "Holdout AUC",
        f"{churn['auc']:.3f}",
        sub="0.50 = coin flip · higher is better",
    )
with model_cards[1]:
    theme.kpi_card(
        "Base churn",
        f"{churn['base_churn']:.1%}",
        sub=f"{churn['n_test']:,} test customers · 12-month label",
    )
with model_cards[2]:
    theme.kpi_card(
        "Predicted churn",
        f"{churn['predicted_churn']:.1%}",
        sub="average model score in the holdout",
    )
with model_cards[3]:
    theme.kpi_card(
        "Accuracy",
        f"{churn['accuracy']:.1%}",
        sub="majority-class baseline · not evidence of skill",
    )

st.warning(analytics.discrimination_note(float(churn["auc"])))

decile_table = churn["deciles"].copy()
decile_table["actual_churn"] *= 100
decile_table["predicted_churn"] *= 100
left, right = st.columns((2, 3))
with left:
    st.markdown("##### Holdout deciles")
    st.dataframe(
        decile_table,
        hide_index=True,
        column_config={
            "decile": st.column_config.NumberColumn("Decile", format="%.0f"),
            "customers": st.column_config.NumberColumn("Customers", format="%.0f"),
            "actual_churn": st.column_config.NumberColumn("Actual churn (%)", format="%.1f"),
            "predicted_churn": st.column_config.NumberColumn("Predicted churn (%)", format="%.1f"),
        },
    )
    st.caption(
        "If the model worked, actual churn would rise from decile 1 to 10. Here it "
        "is flat at roughly 35–36% in every decile."
    )
with right:
    st.markdown("##### Logistic coefficients")
    coef = churn["coefficients"].copy()
    st.dataframe(
        coef,
        hide_index=True,
        column_config={
            "term": st.column_config.TextColumn("Term"),
            "coef": st.column_config.NumberColumn("Coefficient", format="%.4f"),
            "se": st.column_config.NumberColumn("SE", format="%.4f"),
            "z": st.column_config.NumberColumn("z", format="%.3f"),
            "p": st.column_config.NumberColumn("p-value", format="%.3f"),
        },
    )
    st.caption(
        f"Train n = {churn['n_train']:,} · test n = {churn['n_test']:,}. No "
        "behavioural feature is significant at 5%; the intercept carries the "
        "model. This is a failed prediction, reported as such."
    )

# ------------------------------------------------------ governorate CLV table --
gov_table = governorates.copy()
theme.section_header("Top-10 governorates by historical CLV")
st.dataframe(
    gov_table,
    hide_index=True,
    column_config={
        "governorate_ar": st.column_config.TextColumn("Governorate"),
        "buyers": st.column_config.NumberColumn("Buyers", format="%.0f"),
        "clv": st.column_config.NumberColumn("Historical CLV (EGP)", format="%.0f"),
        "median_clv": st.column_config.NumberColumn("Median CLV (EGP)", format="%.0f"),
    },
)

with st.expander("Definitions, model result and what not to do (audit A12)", expanded=False):
    st.markdown(
        "- **CLV** = lifetime gross profit (`gross_profit_lifetime`), not a "
        "forward-looking value. It excludes acquisition cost, retention cost, "
        "discounting, working capital and guests (audit A4).\n"
        "- **Churn definition**: no purchase for 365+ days, among customers with "
        "365+ days of tenure. Never-purchased catalog customers (10,340) and "
        "insufficient-history customers (3,842) are reported separately and are "
        "not in the churn rate.\n"
        "- **Holdout design**: features are built strictly before each cutoff; the "
        "label is any purchase in the next 365 days. Train cutoff 2024-10-18, test "
        "cutoff 2025-10-18. The test period ends at the dataset edge (2026-10-18), "
        "so the test label window is complete.\n"
        f"- **Result**: AUC **{churn['auc']:.3f}**, accuracy {churn['accuracy']:.1%} "
        f"against a base churn of {churn['base_churn']:.1%}. Accuracy equals the "
        "majority-class baseline; the deciles are flat. The model has no usable "
        "discrimination.\n"
        "- **Why**: the observed features (recency, frequency, monetary, tenure, "
        "AOV, segment) do not separate future repurchasers. Twelve-month "
        "repurchase is ~64% in every recency bucket. This looks like a data "
        "generation characteristic, not a modelling bug.\n"
        "- **Do not** use the model score to rank customers, target retention "
        "spend, or claim predictive CLV. Use the descriptive churn status for "
        "operational follow-up, with the caveat that it is a definition, not a "
        "prediction."
    )
