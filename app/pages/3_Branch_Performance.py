"""Branch & Governorate Performance (deck p.4) - store league table + growth.

US4 / tasks T060-T063. Branch growth compares the selected window against the
same calendar-span one year earlier; branches/locations with no prior-window
sales (new, or dataset started mid-window) show 'n/a', never a fake 0%.
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import data, global_filters, theme
from app.filters import (
    DATA_END,
    previous_period,
    selected_period,
    window_label,
)

start, end, label, mode = selected_period()

# Global cross-filters (App Shell v3): channel + branch scope this page;
# governorate stays unfiltered so the governorate share/growth charts
# always compare the full set.
_gf_where, _gf_params = global_filters.sales_where({"channel", "branch"})
prev_window = previous_period(start, end, mode)


# ----------------------------------------------------------------- queries ---
def _branch_agg(window: tuple) -> pd.DataFrame:
    s, e = window
    frame = data.q(
        """
        SELECT branch_id,
               ANY_VALUE(branch_name_ar)          AS branch,
               ANY_VALUE(branch_governorate_ar)   AS governorate,
               SUM(net_sales)                     AS net,
               COUNT(DISTINCT sales_order_id)     AS orders,
               COUNT(DISTINCT customer_id)        AS customers
        FROM views.sales_enriched
        WHERE order_date BETWEEN ? AND ?{_gf_where}
        GROUP BY branch_id
        """,
        (s, e) + _gf_params,
    )
    frame["aov"] = frame.net / frame.orders.where(frame.orders > 0, np.nan)
    return frame


cur_b = _branch_agg((start, end))
if prev_window:
    prior_b = _branch_agg(prev_window)
    cur_b = cur_b.merge(
        prior_b[["branch_id", "net"]].rename(columns={"net": "prior_net"}),
        on="branch_id", how="left",
    )
else:
    cur_b["prior_net"] = np.nan
cur_b["growth"] = np.where(
    cur_b.prior_net.fillna(0) > 0, cur_b.net / cur_b.prior_net - 1.0, np.nan
)
cur_b = cur_b.sort_values("net", ascending=False).reset_index(drop=True)
cur_b["rank"] = cur_b.index + 1

theme.page_header(
    "Branch & Governorate Performance",
    f"Reporting period: **{label}** · {len(cur_b)} active branches · "
    f"growth = same calendar-span one year earlier · data through {DATA_END.isoformat()}",
    eyebrow="Commercial performance",
    badges=('Store league table',),
)
global_filters.render_filter_bar({"channel", "branch"})

prev_label = window_label(prev_window, empty="no window")

k_net = float(cur_b.net.sum())
k_net_prior = float(cur_b.prior_net.sum()) if prev_window else None
k_orders = int(cur_b.orders.sum())
k_aov = k_net / max(k_orders, 1)
k_active = int((cur_b.net > 0).sum())

cards = st.columns(4)
for col, (title, value, sub, tone) in zip(
    cards,
    [
        ("Net sales", theme.fmt_egp(k_net), f"vs {prev_label}" if prev_window else "all-time window", "blue"),
        ("Active branches", str(k_active), f"of {len(cur_b)} with sales in window", "teal"),
        ("Avg branch net", theme.fmt_egp(k_net / max(k_active, 1)), "mean net of active branches", "violet"),
        ("Basket (AOV)", theme.fmt_egp(k_aov), "network-wide, guests included", "amber"),
    ],
    strict=True,
):
    with col:
        theme.kpi_card(title, value, sub=sub, tone=tone)

st.divider()

# ------------------------------------------- ranked table w/ colors (T060) --
table = cur_b[["branch", "governorate", "net", "growth", "orders", "aov"]].copy()
table["growth"] = table.growth.map(lambda v: "n/a" if pd.isna(v) else f"{v:+.1%}")
styled = table.style.map(
    lambda v: f"color: {theme.TEXT_MUTED};" if str(v) == "n/a"
    else f"color: {theme.GOOD if str(v).startswith('+') else theme.BAD}; font-weight: 600;",
    subset=["growth"],
)
st.dataframe(
    styled, hide_index=True,
    column_config={
        "branch": st.column_config.TextColumn("Branch"),
        "governorate": st.column_config.TextColumn("Governorate", width="small"),
        "net": st.column_config.NumberColumn("Net sales (EGP)", format="%.0f"),
        "growth": st.column_config.TextColumn(f"YoY growth ({prev_label})", width="small"),
        "orders": st.column_config.NumberColumn("Orders", format="%.0f"),
        "aov": st.column_config.NumberColumn("Avg basket (EGP)", format="%.0f"),
    },
)
st.caption(
    "Top of the table = highest net in the window. Growth is shown with a direction "
    "arrow and a good/bad status; 'n/a' = branch did not sell in the comparison window "
    "(new or dataset boundary)."
)

# -------------------------------------- governorate revenue + growth (T061) --
gov_c = cur_b.groupby("governorate", as_index=False).agg(
    net=("net", "sum"), prior_net=("prior_net", "sum"), orders=("orders", "sum")
)
gov_c["share"] = gov_c.net / gov_c.net.sum()
gov_c["growth"] = np.where(gov_c.prior_net.fillna(0) > 0, gov_c.net / gov_c.prior_net - 1.0, np.nan)
gov_c = gov_c.sort_values("net", ascending=False)

gov_col, sc_col = st.columns([1, 1])

gov_fig = go.Figure(go.Bar(
    x=gov_c.share, y=gov_c.governorate, orientation="h",
    marker={"color": gov_c.growth.fillna(0),
            "colorscale": [[0.0, theme.BAD], [0.5, theme.NEUTRAL], [1.0, theme.GOOD]],
            "cmin": -0.3, "cmax": 0.3, "showscale": False},
    text=[theme.fmt_pct(s) + (f" ({g:+.0%})" if pd.notna(g) else "")
          for s, g in zip(gov_c.share, gov_c.growth, strict=True)],
    textposition="inside",
    customdata=np.stack([gov_c.net, gov_c.growth.fillna(np.nan)], axis=-1),
    hovertemplate="%{y}: %{x:.1%} of window net (EGP %{customdata[0]:,.0f})"
                  "<extra></extra>",
))
gov_fig.update_layout(title="Governorate share of net sales — color = YoY growth")
theme.apply_plotly_style(gov_fig)
gov_fig.update_yaxes(autorange="reversed")

# -------------------------------- growth vs revenue scatter (T062) --
sc = cur_b[cur_b.growth.notna()].copy()
median_net = float(sc.net.median())
median_growth = float(sc.growth.median())

sc_fig = go.Figure(go.Scatter(
    x=sc.net, y=sc.growth, mode="markers",
    marker={
        "size": np.sqrt(sc.orders) * 3.0 + 6.0,
        "color": [theme.GOOD if g >= 0 else theme.BAD for g in sc.growth],
        "opacity": 0.8,
        "line": {"color": theme.TEXT, "width": 0.5},
    },
    customdata=np.stack([sc.branch, sc.governorate, sc.growth], axis=-1),
    hovertemplate="%{customdata[0]} (%{customdata[1]})<br>"
                  "Net: EGP %{x:,.0f}<br>Growth: %{customdata[2]:+.1%}<extra></extra>",
))
sc_fig.add_hline(y=median_growth, line={"color": theme.TEXT_MUTED, "width": 1, "dash": "dot"})
sc_fig.add_vline(x=median_net, line={"color": theme.TEXT_MUTED, "width": 1, "dash": "dot"})
sc_fig.update_layout(title="Branch quadrants — net (x) vs YoY growth (y); dot size = orders")
theme.apply_plotly_style(sc_fig)

with gov_col:
    st.plotly_chart(gov_fig, width="stretch", config={"displayModeBar": False})
with sc_col:
    st.plotly_chart(sc_fig, width="stretch", config={"displayModeBar": False})

# -------------------------------------------------------- notes (T063) --
guest_orders = data.scalar(
    """
    SELECT COUNT(DISTINCT sales_order_id) FROM views.sales_enriched
    WHERE customer_id IS NULL AND order_date BETWEEN ? AND ?{_gf_where}
    """,
    (start, end) + _gf_params,
) or 0

with st.expander("Data notes - definitions & caveats for this page", expanded=False):
    st.markdown(
        f"""
- **Grain**: one row per `branch_id` that sold in the window; aggregates taken straight
  from the `views.sales_enriched` spine (80 branches exist in the catalog; only active ones can rank).
- **Growth** = net(window) / net(same calendar-span one year earlier) − 1, per branch /
  governorate. 'n/a' means no prior-window sales — new branches and, e.g., year-2019
  windows reaching before the dataset start (Oct 2018). We never print 0% there.
- **Quadrant scatter** imitates deck p.4's growth-vs-size view: dot position = revenue
  and growth; dot size = orders. Dashed lines mark window medians. Red dots shrinking
  green dots are *branches below median net but growing*, and vice versa.
- **Governorate bar** colors encode growth (red→blue→green over ±30%); its share
  numerators use the whole window net.
- **Guests**: {int(guest_orders):,} guest orders in the window count in branch revenue
  but not in the customers column (A4 — column shows logged-in buyers only).
- **Currency EGP; VAT shown nowhere here** — all figures are pre-VAT net line values.
"""
    )
