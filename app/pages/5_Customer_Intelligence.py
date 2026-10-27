"""Customer Intelligence + CLV & Churn (deck p.7,19) - RFM, profiles, CLV, churn.

US6 (tab 1) and S19 (tab 2) share one page since the 2026-10 UI refactor. RFM
metrics and tiers are computed as of the dataset end (2026-10-18, audit A5) -
they are profile facts, so they do NOT change with the sidebar period.
Window-scoped metrics (active / repeat) respect the selector. CLV is
historical gross profit, not a forecast; churn is defined as no purchase for
365 days among customers with at least 365 days of tenure, and the temporal
holdout is reported even though it fails (A12).

Each tab renders through its own function: the two blocks both use names like
`buyer_share` / `catalog` with different meanings, so sharing one frame would
shadow them. Page bodies are otherwise verbatim from the standalone pages.
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from app import analytics, data, global_filters, theme
from app.filters import DATA_END, selected_period

start, end, label, _ = selected_period()

# Global cross-filters (App Shell v3): applied ONLY to the window-scoped
# sales query in the Customer Intelligence tab (active / repeat buyers).
# RFM tiers, CLV and the churn holdout are profile facts computed as of
# the dataset end — immutable by design (A5) — so they stay unfiltered.
_GF_SUPPORTED = {"governorate", "channel", "branch"}
_gf_where, _gf_params = global_filters.sales_where(_GF_SUPPORTED)









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

def _render_ci() -> None:
    theme.page_header(
        "Customer Intelligence",
        f"Window-scoped metrics use **{label}**; RFM tiers are profile facts as of "
        f"{DATA_END.isoformat()} (immutable by design, A5) · guests excluded per A4",
        eyebrow="Customers",
        badges=('RFM profile facts',),
    )


    # ---------------------------------------------------------------- KPIs (T082) --
    window_stats = data.q(
        """
        WITH per_customer AS (
            SELECT customer_id, COUNT(DISTINCT sales_order_id) AS orders
            FROM views.sales_enriched
            WHERE order_date BETWEEN ? AND ?
            """ + _gf_where + """
              AND customer_id IS NOT NULL
            GROUP BY customer_id
        )
        SELECT COUNT(*) AS active,
               COUNT(*) FILTER (WHERE orders >= 2) AS repeat_customers,
               SUM(orders) AS orders_total
        FROM per_customer
    """, (start, end) + _gf_params).iloc[0]
    new_signups = data.scalar(
        "SELECT COUNT(*) FROM views.customer_profile WHERE joined_date BETWEEN ? AND ?",
        (start, end),
    ) or 0

    catalog = data.q(
        """
        SELECT COUNT(*) AS customers,
               COUNT(*) FILTER (WHERE rfm_tier <> 'No purchase') AS buyers,
               COUNT(*) FILTER (WHERE rfm_tier = 'No purchase') AS never_bought
        FROM views.customer_profile
    """).iloc[0]

    repeat_rate = float(window_stats.repeat_customers) / max(float(window_stats.active), 1)
    k_cards = st.columns(5)
    for col, (title, value, sub, tone) in zip(
        k_cards,
        [
            ("Active customers", theme.fmt_int(float(window_stats.active)), f"bought in {label.split(' (')[0]}", "violet"),
            ("Repeat rate", theme.fmt_pct(repeat_rate),
             f"{int(window_stats.repeat_customers):,} with \u22652 orders in window", "teal"),
            ("New catalog sign-ups", theme.fmt_int(float(new_signups)), "joined within window", "green"),
            ("Catalog customers", f"{int(catalog.customers):,}", "85K marketing catalog · all-time", "blue"),
            ("Never purchased", theme.fmt_pct(float(catalog.never_bought) / float(catalog.customers)),
             f"{int(catalog.never_bought):,} catalog-only (no order)", "amber"),
        ],
        strict=True,
    ):
        with col:
            theme.kpi_card(title, value, sub=sub, tone=tone)

    # Insights-first strip (App Shell v3): from the window stats above.
    theme.insight_strip([
        {
            "icon": "\U0001F501", "label": "Repeat rate",
            "value": theme.fmt_pct(repeat_rate),
            "sub": f"{int(window_stats.repeat_customers):,} of {int(window_stats.active):,} active customers ordered 2+ times",
            "tone": "good" if repeat_rate >= 0.3 else "warn",
        },
        {
            "icon": "\U0001F464", "label": "Active customers",
            "value": theme.fmt_int(float(window_stats.active)),
            "sub": "identified buyers in the selected window (guests excluded, A4)",
            "tone": "neutral",
        },
        {
            "icon": "\U0001F195", "label": "New sign-ups",
            "value": theme.fmt_int(float(new_signups)),
            "sub": "catalog sign-ups joined within the window",
            "tone": "good" if new_signups else "neutral",
        },
    ])

    st.divider()

    # ------------------------------------------------- profile mix donuts (T080) --
    seg = data.q(
        "SELECT customer_segment AS name, COUNT(*) AS customers FROM views.customer_profile "
        "GROUP BY 1 ORDER BY 2 DESC"
    )
    age = data.q(
        "SELECT COALESCE(age_band, 'Unspecified') AS name, COUNT(*) AS customers "
        "FROM views.customer_profile GROUP BY 1 ORDER BY 2 DESC"
    )
    gov = data.q(
        "SELECT COALESCE(governorate_ar, 'Unspecified') AS name, COUNT(*) AS customers "
        "FROM views.customer_profile GROUP BY 1 ORDER BY 2 DESC"
    )

    donut_figs = []
    for frame, title in ((seg, "By segment"), (age, "By age band"), (gov, "By governorate")):
        fig = go.Figure(go.Pie(
            hole=0.55, labels=frame.name, values=frame.customers,
            marker={"colors": theme.COLORS}, textinfo="percent",
            customdata=frame.customers,
            hovertemplate="%{label}: %{customdata:,} customers (%{percent})<extra></extra>",
        ))
        if title == "By age band":
            # Keep the right-hand 20% slice label inside the card in the narrow
            # three-column layout; the other pies have labels on safe edges.
            fig.update_traces(domain={"x": [0.02, 0.86], "y": [0.04, 0.96]})
        fig.update_layout(title=title)
        theme.apply_plotly_style(fig)
        donut_figs.append(fig)

    c1, c2, c3 = st.columns(3)
    for col, fig in zip((c1, c2, c3), donut_figs, strict=True):
        with col:
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    # --------------------------------------------------- RFM tier table (T081) --
    rfm = data.q(
        """
        SELECT rfm_tier AS tier, COUNT(*) AS customers,
               SUM(lifetime_value) AS lifetime_value,
               AVG(orders_lifetime) AS avg_orders,
               AVG(recency_days) AS avg_recency
        FROM views.customer_profile
        GROUP BY 1
        ORDER BY lifetime_value DESC
        """,
    )
    rfm["share_pct"] = rfm.customers / rfm.customers.sum() * 100.0

    theme.section_header(f"RFM tiers — computed as of dataset end ({DATA_END.isoformat()})")
    st.dataframe(
        rfm, hide_index=True,
        column_config={
            "tier": st.column_config.TextColumn("Tier"),
            "customers": st.column_config.NumberColumn("Customers", format="%.0f"),
            "share_pct": st.column_config.NumberColumn("Share (%)", format="%.1f"),
            "lifetime_value": st.column_config.NumberColumn("Σ lifetime value (EGP)", format="%.0f"),
            "avg_orders": st.column_config.NumberColumn("Avg orders", format="%.1f"),
            "avg_recency": st.column_config.NumberColumn("Avg recency (days)", format="%.0f"),
        },
    )

    # ------------------------------------ top customers by lifetime value (T082) --
    top_c = data.q(
        """
        SELECT customer_id, customer_name_ar AS name, customer_segment AS segment,
               governorate_ar AS governorate, rfm_tier AS tier,
               orders_lifetime AS orders, lifetime_value
        FROM views.customer_profile
        WHERE rfm_tier <> 'No purchase'
        ORDER BY lifetime_value DESC LIMIT 10
        """
    )
    theme.section_header("Top-10 customers by lifetime value")
    st.dataframe(
        top_c, hide_index=True,
        column_config={
            "customer_id": st.column_config.TextColumn("ID", width="small"),
            "name": st.column_config.TextColumn("Customer"),
            "segment": st.column_config.TextColumn("Segment", width="small"),
            "governorate": st.column_config.TextColumn("Governorate", width="small"),
            "tier": st.column_config.TextColumn("RFM tier", width="small"),
            "orders": st.column_config.NumberColumn("Orders", format="%.0f"),
            "lifetime_value": st.column_config.NumberColumn("Lifetime value (EGP)", format="%.0f"),
        },
    )

    # ------------------------------------------------- customer lookup (T083) --
    with st.expander("Customer lookup - order history", expanded=False):
        query = st.text_input("Search by Arabic name fragment or customer id", value="")
        if query.strip():
            like = f"%{query.strip()}%"
            matches = data.q(
                """
                SELECT customer_id, customer_name_ar AS name, rfm_tier AS tier,
                       orders_lifetime AS orders, lifetime_value
                FROM views.customer_profile
                WHERE customer_name_ar LIKE ? OR CAST(customer_id AS VARCHAR) LIKE ?
                ORDER BY lifetime_value DESC LIMIT 8
                """,
                (like, like),
            )
            if matches.empty:
                st.info("No customer matches that search.")
            else:
                name_map = dict(zip(matches.customer_id, matches.name, strict=True))
                match_id = st.selectbox(
                    "Pick a customer to load history",
                    matches.customer_id.tolist(),
                    format_func=lambda cid_in: f"{name_map[cid_in]} ({cid_in})",
                )
                history = data.q(
                    """
                    SELECT CAST(order_date AS DATE) AS date, sales_order_id AS order_id,
                           SUM(net_sales) AS net_egp, COUNT(*) AS lines,
                           MAX(sales_channel) AS channel
                    FROM views.sales_enriched
                    WHERE customer_id = ?
                    GROUP BY order_date, sales_order_id
                    ORDER BY order_date DESC LIMIT 20
                    """,
                    (str(match_id),),
                )
                st.dataframe(
                    history, hide_index=True,
                    column_config={
                        "date": st.column_config.DateColumn("Date"),
                        "order_id": st.column_config.TextColumn("Order"),
                        "net_egp": st.column_config.NumberColumn("Net (EGP)", format="%.0f"),
                        "lines": st.column_config.NumberColumn("Lines", format="%.0f"),
                        "channel": st.column_config.TextColumn("Channel", width="small"),
                    },
                )
        else:
            st.caption("Type a fragment of an Arabic name (or a numeric id) to search the 85K customer catalog.")

    # -------------------------------------------------------- notes (T084) --
    guest_orders_total = data.scalar(
        "SELECT COUNT(*) FROM raw.sales_orders WHERE customer_id IS NULL"
    ) or 0

    with st.expander("Data notes - definitions & caveats for this page", expanded=False):
        st.markdown(
            f"""
    - **RFM (metric + tier)**: recency = days since the customer's last order measured
      from **{DATA_END.isoformat()}**; frequency = lifetime distinct orders; monetary = Σ
      net-before-tax across those orders. Quintiles via NTILE(5) on the actual buyers;
      tier labels follow deck p.19 (Champions / Loyal / Potential Loyalist / Need Attention /
      At Risk / Churned). **These are profile facts and do not move with the period selector.**
    - **Active customers (window)** = distinct logged-in buyers with \u22651 order in the
      selected window; **Repeat rate** = share of them with \u22652 orders in the same window.
      Guest orders ({int(guest_orders_total):,} all-time, no customer id) appear nowhere on
      this page (A4) — they are counted in revenue pages only.
    - **Never purchased** uses the marketing catalog (`customer_profile`), not sales.
    - **Sign-up/mix donuts** come from catalog fields (`customer_segment`, `age_band`,
      `governorate_ar`), not purchase behavior.
    - **Lookup** searches name/ID only, over exactly what the dataset ships; history shows
      the customer's last 20 orders (net before VAT).
    - **Currency EGP; all value columns exclude the 14% VAT**.
    """
        )

def _render_clv() -> None:
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
            tone="violet",
        )
    with cards[1]:
        theme.kpi_card(
            "Historical CLV",
            theme.fmt_egp(float(profile.clv)),
            sub="lifetime gross profit across identified buyers · excludes guests",
            tone="blue",
        )
    with cards[2]:
        theme.kpi_card(
            "Median buyer CLV",
            theme.fmt_egp(float(profile.median_clv)),
            sub=f"top 10% of buyers hold {top_decile_share:.1%} of historical CLV",
            tone="teal",
        )
    with cards[3]:
        theme.kpi_card(
            "Churn rate",
            f"{churn_rate:.1%}",
            sub=f"{churned:,} of {eligible:,} eligible buyers · 365+ days since last order",
            tone="red",
        )

    # Insights-first strip (App Shell v3): profile facts, as-of dataset end.
    theme.insight_strip([
        {
            "icon": "\U0001F4B0", "label": "CLV concentration",
            "value": f"top 10% hold {top_decile_share:.1%}",
            "sub": "of historical CLV (lifetime gross profit)",
            "tone": "warn" if top_decile_share >= 0.5 else "neutral",
        },
        {
            "icon": "\U0001F6AA", "label": "Churn rate",
            "value": f"{churn_rate:.1%}",
            "sub": f"{churned:,} of {eligible:,} eligible buyers inactive 365+ days",
            "tone": "bad" if churn_rate >= 0.3 else "warn",
        },
        {
            "icon": "\U0001F6D2", "label": "Buyer share",
            "value": f"{buyer_share:.1%}",
            "sub": f"{buyers:,} of {catalog:,} cataloged customers have purchased",
            "tone": "neutral",
        },
    ])

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
            tone="violet",
        )
    with model_cards[1]:
        theme.kpi_card(
            "Base churn",
            f"{churn['base_churn']:.1%}",
            sub=f"{churn['n_test']:,} test customers · 12-month label",
            tone="teal",
        )
    with model_cards[2]:
        theme.kpi_card(
            "Predicted churn",
            f"{churn['predicted_churn']:.1%}",
            sub="average model score in the holdout",
            tone="amber",
        )
    with model_cards[3]:
        theme.kpi_card(
            "Accuracy",
            f"{churn['accuracy']:.1%}",
            sub="majority-class baseline · not evidence of skill",
            tone="green",
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

global_filters.render_filter_bar(_GF_SUPPORTED)

ci_tab, clv_tab = st.tabs(["Customer Intelligence", "CLV & Churn"])

with ci_tab:
    _render_ci()

with clv_tab:
    _render_clv()
