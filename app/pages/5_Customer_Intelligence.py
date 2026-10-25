"""Customer Intelligence (deck p.7,19) - RFM segments, profiles, lookup.

US6 / tasks T080-T084. RFM metrics and tiers are computed as of the dataset end
(2026-10-18, audit A5) - they are profile facts, so they do NOT change with the
sidebar period. Window-scoped metrics (active / repeat) respect the selector.
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import plotly.graph_objects as go
import streamlit as st

from app import data, theme
from app.filters import DATA_END, previous_period, render_period_selector

st.set_page_config(
    page_title="Customer Intelligence · Cottonil",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.apply_theme()

start, end, label, mode = render_period_selector()
prev_window = previous_period(start, end, mode)

st.title("👥 Customer Intelligence")
st.caption(
    f"Window-scoped metrics use **{label}**; RFM tiers are profile facts as of "
    f"{DATA_END.isoformat()} (immutable by design, A5) · guests excluded per A4"
)

# ---------------------------------------------------------------- KPIs (T082) --
window_stats = data.q(
    """
    WITH per_customer AS (
        SELECT customer_id, COUNT(DISTINCT sales_order_id) AS orders
        FROM views.sales_enriched
        WHERE order_date BETWEEN ? AND ? AND customer_id IS NOT NULL
        GROUP BY customer_id
    )
    SELECT COUNT(*) AS active,
           COUNT(*) FILTER (WHERE orders >= 2) AS repeat_customers,
           SUM(orders) AS orders_total
    FROM per_customer
""", (start, end)).iloc[0]
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
for col, (title, value, sub) in zip(
    k_cards,
    [
        ("Active customers", theme.fmt_int(float(window_stats.active)), f"bought in {label.split(' (')[0]}"),
        ("Repeat rate", theme.fmt_pct(repeat_rate),
         f"{int(window_stats.repeat_customers):,} with \u22652 orders in window"),
        ("New catalog sign-ups", theme.fmt_int(float(new_signups)), "joined within window"),
        ("Catalog customers", f"{int(catalog.customers):,}", "85K marketing catalog · all-time"),
        ("Never purchased", theme.fmt_pct(float(catalog.never_bought) / float(catalog.customers)),
         f"{int(catalog.never_bought):,} catalog-only (no order)"),
    ],
    strict=True,
):
    with col:
        theme.kpi_card(title, value, sub=sub)

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
        marker={"colors": theme.COLORS}, textinfo="percent", textfont={"color": theme.TEXT},
        customdata=frame.customers,
        hovertemplate="%{label}: %{customdata:,} customers (%{percent})<extra></extra>",
    ))
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

st.markdown(f"#### RFM tiers — computed as of dataset end ({DATA_END.isoformat()})")
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
st.markdown("#### Top-10 customers by lifetime value")
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
with st.expander("🔍 Customer lookup - order history", expanded=False):
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
