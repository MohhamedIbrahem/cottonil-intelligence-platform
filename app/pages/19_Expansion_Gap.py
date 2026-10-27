"""Store Expansion (Gap Proxy) (S12) - governorate coverage intensity.

There is no site-selection data: no demographics, competitors, rent, catchment,
cannibalisation or store health. Every governorate already has at least one
branch. This page therefore reports a deliberately narrow coverage proxy and
keeps the weak signal visible.
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import plotly.graph_objects as go
import streamlit as st

from app import data, theme
from app.filters import DATA_END  # sidebar period does not scope this page

gap = data.q(
    """
    SELECT governorate_ar, branches, retail_branches, reseller_pos_branches,
           customers, resident_buyers, buyer_penetration, resident_orders,
           orders_per_buyer, resident_net_sales, resident_net_sales_per_buyer,
           branch_orders, branch_net_sales, pos_orders, pos_net_sales,
           resident_buyers_per_branch, resident_net_sales_per_branch,
           pos_net_sales_per_branch, network_share, customer_share, buyer_share,
           resident_sales_share, pos_sales_share, network_minus_buyer_share_pp
    FROM views.expansion_gap
    ORDER BY resident_buyers_per_branch DESC
    """
)

total_branches = int(gap.branches.sum())
total_customers = int(gap.customers.sum())
total_buyers = int(gap.resident_buyers.sum())
retail_branches = int(gap.retail_branches.sum())
reseller_pos_branches = int(gap.reseller_pos_branches.sum())
national_buyers_per_branch = total_buyers / total_branches
pos_per_branch = float(gap.pos_net_sales.sum()) / total_branches
corr = float(gap.resident_buyers_per_branch.corr(gap.pos_net_sales_per_branch))

theme.page_header(
    "Store Expansion (Gap Proxy)",
    f"**{len(gap)} governorates** · all already have at least one branch · residence-based "
    "demand proxy, not catchment · no demographics, competitors, rent, cannibalisation or "
    "store-health data · sidebar period does not change this page · "
    f"data through {DATA_END.isoformat()}",
    eyebrow="Advanced analytics",
    badges=(('Coverage proxy', 'warn'),),
)

st.warning(
    "This is a coverage-intensity proxy, not a site-selection model. The dataset has no "
    "market potential, competitor, rent or cannibalisation inputs, and every governorate "
    "already has a branch (audit A17)."
)

cards = st.columns(4)
with cards[0]:
    theme.kpi_card(
        "Governorates with a branch",
        f"{len(gap)} / {len(gap)}",
        sub="no greenfield whitespace · one branch minimum",
        tone="teal",
    )
with cards[1]:
    theme.kpi_card(
        "Branches",
        theme.fmt_int(total_branches),
        sub=f"{retail_branches} retail · {reseller_pos_branches} POS/reseller",
        tone="blue",
    )
with cards[2]:
    theme.kpi_card(
        "Resident buyers per branch",
        theme.fmt_int(national_buyers_per_branch),
        sub=f"{theme.fmt_int(total_buyers)} buyers ÷ {total_branches} branches · range 168–3,530",
        tone="violet",
    )
with cards[3]:
    theme.kpi_card(
        "Branch POS per branch",
        theme.fmt_egp(pos_per_branch),
        sub="Retail POS only · range EGP 5.06M–5.28M · nearly uniform",
        tone="rose",
    )

# Insights-first strip (App Shell v3): from the gap table above (sorted by
# resident buyers per branch, descending).
theme.insight_strip([
    {
        "icon": "\U0001F4CD", "label": "Thinnest coverage",
        "value": f"{gap.iloc[-1].governorate_ar} · {theme.fmt_int(float(gap.iloc[-1].resident_buyers_per_branch))} buyers/branch",
        "sub": "fewest resident buyers per branch — the weakest coverage intensity",
        "tone": "warn",
    },
    {
        "icon": "\U0001F3EA", "label": "Densest coverage",
        "value": f"{gap.iloc[0].governorate_ar} · {theme.fmt_int(float(gap.iloc[0].resident_buyers_per_branch))} buyers/branch",
        "sub": "most resident buyers per branch in the network",
        "tone": "neutral",
    },
    {
        "icon": "\U0001F517", "label": "Coverage vs POS sales",
        "value": f"r = {corr:.2f}",
        "sub": "correlation between buyers/branch and POS net/branch — a proxy, not a model (A17)",
        "tone": "neutral",
    },
])

st.divider()

left, right = st.columns((3, 2))

with left:
    chart = gap.copy()
    chart["network_share_pct"] = chart.network_share * 100
    chart["buyer_share_pct"] = chart.buyer_share * 100
    chart = chart.sort_values("network_minus_buyer_share_pp")
    colors = [
        theme.ACCENT if value >= 0 else theme.ACCENT_2
        for value in chart.network_minus_buyer_share_pp
    ]
    gap_fig = go.Figure(
        go.Bar(
            x=chart.network_minus_buyer_share_pp,
            y=chart.governorate_ar,
            orientation="h",
            marker_color=colors,
            customdata=chart[["branches", "resident_buyers", "network_share_pct", "buyer_share_pct"]],
            hovertemplate=(
                "%{y}<br>Gap %{x:+.1f} pp"
                "<br>Branches %{customdata[0]:,.0f}"
                "<br>Resident buyers %{customdata[1]:,.0f}"
                "<br>Network share %{customdata[2]:.1f}% · buyer share %{customdata[3]:.1f}%"
                "<extra></extra>"
            ),
        )
    )
    gap_fig.add_vline(x=0, line={"color": theme.TEXT_MUTED, "width": 1})
    gap_fig.update_layout(
        title="Branch-network share minus resident-buyer share",
        xaxis_title="Percentage points",
        yaxis_title="",
        height=540,
        showlegend=False,
    )
    theme.apply_plotly_style(gap_fig)
    st.plotly_chart(gap_fig, width="stretch", config={"displayModeBar": False})
    st.caption(
        "Positive = a larger share of branches than of resident buyers; negative = fewer. "
        "Cairo (+21.5 pp), Alexandria (+7.7) and Giza (+2.8) carry the network; the three "
        "one-branch governorates are about −3.5 pp. Because resident customers are near-uniform, "
        "this is a branch-count diagnostic, not market potential."
    )

with right:
    scatter = go.Figure(
        go.Scatter(
            x=gap.resident_buyers_per_branch,
            y=gap.pos_net_sales_per_branch / 1e6,
            mode="markers",
            marker={
                "color": theme.ACCENT,
                "size": 8 + gap.branches * 0.8,
                "opacity": 0.75,
            },
            customdata=gap[["governorate_ar", "branches", "resident_net_sales", "pos_net_sales"]],
            hovertemplate=(
                "%{customdata[0]}"
                "<br>Resident buyers/branch %{x:,.0f}"
                "<br>POS per branch EGP %{y:,.2f}M"
                "<br>Branches %{customdata[1]:,.0f}"
                "<br>Resident net EGP %{customdata[2]:,.0f}"
                "<br>POS net EGP %{customdata[3]:,.0f}<extra></extra>"
            ),
        )
    )
    scatter.add_hline(
        y=pos_per_branch / 1e6,
        line={"color": theme.TEXT_MUTED, "width": 1, "dash": "dot"},
        annotation_text=f"national average EGP {pos_per_branch / 1e6:.2f}M",
        annotation_position="top left",
    )
    scatter.update_layout(
        title="Buyer load vs branch POS sales per branch",
        xaxis={"title": "Resident buyers per branch"},
        yaxis={"title": "POS net sales per branch (EGP M)"},
        showlegend=False,
    )
    theme.apply_plotly_style(scatter)
    st.plotly_chart(scatter, width="stretch", config={"displayModeBar": False})
    st.caption(
        f"r = {corr:.2f}; no meaningful association. POS per branch stays between EGP 5.06M "
        "and 5.28M regardless of resident buyer load. Marker size = branch count. Store sales "
        "per branch are nearly uniform in this dataset."
    )

st.divider()

theme.section_header("Governorate coverage table")
table = gap.copy()
for column in (
    "resident_net_sales",
    "resident_net_sales_per_branch",
    "pos_net_sales",
    "pos_net_sales_per_branch",
):
    table[column] = table[column] / 1e6
for column in ("buyer_penetration", "network_share", "buyer_share"):
    table[column] = table[column] * 100
table = table.sort_values("resident_buyers_per_branch", ascending=False)
table = table.rename(
    columns={
        "governorate_ar": "Governorate",
        "branches": "Branches",
        "customers": "Customers",
        "resident_buyers": "Resident buyers",
        "buyer_penetration": "Buyer penetration (%)",
        "resident_net_sales": "Resident net sales (EGP M)",
        "resident_net_sales_per_branch": "Resident net / branch (EGP M)",
        "pos_net_sales": "POS net sales (EGP M)",
        "pos_net_sales_per_branch": "POS net / branch (EGP M)",
        "resident_buyers_per_branch": "Buyers / branch",
        "network_share": "Network share (%)",
        "buyer_share": "Buyer share (%)",
        "network_minus_buyer_share_pp": "Gap (pp)",
    }
)
st.dataframe(
    table[
        [
            "Governorate",
            "Branches",
            "Customers",
            "Resident buyers",
            "Buyer penetration (%)",
            "Resident net sales (EGP M)",
            "Resident net / branch (EGP M)",
            "POS net sales (EGP M)",
            "POS net / branch (EGP M)",
            "Buyers / branch",
            "Network share (%)",
            "Buyer share (%)",
            "Gap (pp)",
        ]
    ],
    hide_index=True,
    height=650,
    column_config={
        "Governorate": st.column_config.TextColumn("Governorate"),
        "Branches": st.column_config.NumberColumn("Branches", format="%.0f"),
        "Customers": st.column_config.NumberColumn("Customers", format="%.0f"),
        "Resident buyers": st.column_config.NumberColumn("Resident buyers", format="%.0f"),
        "Buyer penetration (%)": st.column_config.NumberColumn(
            "Buyer penetration (%)", format="%.1f"
        ),
        "Resident net sales (EGP M)": st.column_config.NumberColumn(
            "Resident net sales (EGP M)", format="%.1f"
        ),
        "Resident net / branch (EGP M)": st.column_config.NumberColumn(
            "Resident net / branch (EGP M)", format="%.1f"
        ),
        "POS net sales (EGP M)": st.column_config.NumberColumn(
            "POS net sales (EGP M)", format="%.1f"
        ),
        "POS net / branch (EGP M)": st.column_config.NumberColumn(
            "POS net / branch (EGP M)", format="%.2f"
        ),
        "Buyers / branch": st.column_config.NumberColumn(
            "Buyers / branch", format="%.0f"
        ),
        "Network share (%)": st.column_config.NumberColumn(
            "Network share (%)", format="%.2f"
        ),
        "Buyer share (%)": st.column_config.NumberColumn(
            "Buyer share (%)", format="%.2f"
        ),
        "Gap (pp)": st.column_config.NumberColumn("Gap (pp)", format="%+.2f"),
    },
)
st.caption(
    "Buyer counts exclude guests; branch POS sales include guests. Resident net sales are "
    "all-channel identified-customer sales at the customer's address, not catchment demand. "
    "All 21 governorates already have a branch, so there is no greenfield list."
)

with st.expander("Definitions and limits (audit A17)", expanded=False):
    st.markdown(
        f"- **View**: `views.expansion_gap` has one row per governorate (**{len(gap)}**) and "
        f"covers **{total_branches} branches** (**{retail_branches} retail + "
        f"{reseller_pos_branches} POS/reseller**) and **{total_customers:,} cataloged "
        "customers**.\n"
        f"- **Demand side**: **{total_buyers:,} resident buyers** (3,469–3,648 per "
        "governorate), buyer penetration **87.1–88.6%**, and **EGP 680.3M** resident net "
        "sales (EGP 31.2M–34.0M per governorate). Guests are excluded from buyer and "
        "resident-sales metrics (audit A4).\n"
        "- **Supply side**: branch all-channel net sales **EGP 841.3M** (EGP 9.84M–11.43M per "
        "branch); Retail POS net sales **EGP 416.2M** (EGP 5.06M–5.28M per branch). Every "
        "governorate already has at least one branch, so there is no greenfield whitespace.\n"
        "- **Geography caveat**: **95.2%** of identified order lines have a customer "
        "governorate different from the branch governorate. `branch_id` is not geographic; "
        "resident sales use the customer address, while branch sales use the assigned branch. "
        "They are different lenses and cannot be reconciled as catchment or leakage.\n"
        "- **Uniformity caveat**: resident customer counts are near-uniform (3,956–4,134 per "
        "governorate) and branch POS sales per branch are near-uniform (EGP 5.06M–5.28M). "
        "These look like data-generation characteristics, not market facts. The coverage "
        "ranking is mostly a branch-count ranking: the correlation between buyers per branch "
        "and POS per branch is only **−0.24**.\n"
        "- **Gap definition**: branch-network share minus resident-buyer share, in percentage "
        "points. Positive means more network share than buyer share; negative means less. It "
        "is a descriptive intensity gap, not a score and not a recommendation.\n"
        "- **Missing inputs**: demographics, income, competitor locations, rent, footfall, "
        "catchment, cannibalisation, store health, lease terms, capital cost and local "
        "management capacity. There is no composite site-selection score or ranked expansion "
        "list.\n"
        "- **Use**: frame questions for local validation only. Do not present this proxy as a "
        "market opportunity or an investment case."
    )
