"""Smart Replenishment (Rules-Based) (S18).

A transparent 45-day cover rule on the latest stock snapshot. Branches use
90-day sales velocity; warehouses use outgoing-transfer velocity. The stock
snapshot is category-level, so this cannot produce SKU purchase orders.
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import plotly.graph_objects as go
import streamlit as st

from app import data, theme
from app.filters import DATA_END, render_period_selector

st.set_page_config(
    page_title="Smart Replenishment · Cottonil",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.apply_theme()

_start, _end, _label, _mode = render_period_selector()

SIGNAL_ORDER = [
    "Critical (<14d)",
    "Low (14-30d)",
    "Below target (30-45d)",
    "Adequate (45-180d)",
    "Overstock (>180d)",
    "No demand signal",
]
SIGNAL_COLORS = {
    "Critical (<14d)": theme.BAD,
    "Low (14-30d)": "#C2410C",
    "Below target (30-45d)": theme.WARN,
    "Adequate (45-180d)": theme.GOOD,
    "Overstock (>180d)": theme.ACCENT_2,
    "No demand signal": theme.NEUTRAL,
}
TARGET_DAYS = 45

cells = data.q(
    """
    SELECT year_month, stock_location_id, stock_location_type, location_label,
           location_governorate_ar, product_category, closing_units,
           closing_stock_value, stockout_risk_score, stock_status,
           velocity_90d, velocity_source, cover_days, target_cover_days,
           reorder_units, reorder_value_EGP, signal, action
    FROM views.replenishment_signals
    ORDER BY signal, cover_days
    """
)

locations = st.sidebar.selectbox("Location type", ["All locations", "Branch", "Warehouse"])
categories = sorted(cells.product_category.unique())
category = st.sidebar.selectbox("Category", ["All categories", *categories])
signal_filter = st.sidebar.selectbox("Signal", ["All signals", *SIGNAL_ORDER])

view = cells.copy()
if locations != "All locations":
    view = view[view.stock_location_type == locations]
if category != "All categories":
    view = view[view.product_category == category]
if signal_filter != "All signals":
    view = view[view.signal == signal_filter]

below = view[view.signal.isin(SIGNAL_ORDER[:3])]
critical = view[view.signal == SIGNAL_ORDER[0]]
overstock = view[view.signal == SIGNAL_ORDER[4]]
snapshot_month = str(cells.year_month.max())

theme.page_header(
    "Smart Replenishment",
    f"Latest stock snapshot **{snapshot_month}** · target cover **{TARGET_DAYS} days** · "
    f"{theme.fmt_int(float(len(view)))} of {theme.fmt_int(float(len(cells)))} location-category cells · "
    f"branches use sales velocity, warehouses use outgoing transfers · data through {DATA_END.isoformat()}",
    eyebrow="Planning",
    badges=('45-day cover rule',),
)

cards = st.columns(4)
with cards[0]:
    theme.kpi_card(
        "Below target",
        theme.fmt_int(float(len(below))),
        sub=f"{len(below) / len(view):.1%} of filtered cells have <{TARGET_DAYS} days of cover"
        if len(view)
        else "no cells in the current filter",
    )
with cards[1]:
    theme.kpi_card(
        "Critical (<14 days)",
        theme.fmt_int(float(len(critical))),
        sub="reorder now · lowest cover in the snapshot",
    )
with cards[2]:
    theme.kpi_card(
        "Suggested reorder units",
        theme.fmt_int(float(below.reorder_units.sum())),
        sub=f"to reach {TARGET_DAYS} days of cover · {len(below):,} cells",
    )
with cards[3]:
    theme.kpi_card(
        "Overstock value",
        theme.fmt_egp(float(overstock.closing_stock_value.sum())),
        sub=f"{len(overstock):,} overstock cells · no auto-reorder",
    )

st.divider()

if view.empty:
    st.info("No cells match the current filters. Widen the location, category or signal filter.")
    st.stop()

# ------------------------------------------------------- signal distribution ----
left, right = st.columns((2, 3))

with left:
    counts = (
        view.pivot_table(
            index="signal",
            columns="stock_location_type",
            values="stock_location_id",
            aggfunc="count",
        )
        .reindex(SIGNAL_ORDER)
        .fillna(0)
    )
    signal_fig = go.Figure()
    for location_type, color in (("Branch", theme.ACCENT), ("Warehouse", theme.ACCENT_2)):
        if location_type in counts.columns:
            signal_fig.add_trace(
                go.Bar(
                    x=counts[location_type],
                    y=counts.index,
                    orientation="h",
                    name=location_type,
                    marker_color=color,
                    hovertemplate="%{y}<br>%{x:.0f} cells<extra>%{fullData.name}</extra>",
                )
            )
    signal_fig.update_layout(
        title="Cover signal by location type",
        barmode="stack",
        xaxis_title="Cells",
        yaxis_title="",
        yaxis={"categoryorder": "array", "categoryarray": list(reversed(SIGNAL_ORDER))},
    )
    theme.apply_plotly_style(signal_fig)
    st.plotly_chart(signal_fig, width="stretch", config={"displayModeBar": False})

with right:
    scatter = go.Figure()
    for signal in SIGNAL_ORDER:
        part = view[(view.signal == signal) & view.cover_days.notna()]
        if part.empty:
            continue
        scatter.add_trace(
            go.Scatter(
                x=part.cover_days,
                y=part.velocity_90d,
                mode="markers",
                name=signal,
                marker={"color": SIGNAL_COLORS[signal], "size": 7, "opacity": 0.72},
                customdata=part[["location_label", "product_category", "closing_units", "reorder_units"]],
                hovertemplate=(
                    "%{customdata[0]} · %{customdata[1]}"
                    "<br>Cover %{x:.1f} days · velocity %{y:.2f} units/day"
                    "<br>Closing units %{customdata[2]:,.0f} · reorder %{customdata[3]:,.0f}"
                    "<extra>%{fullData.name}</extra>"
                ),
            )
        )
    scatter.add_vline(
        x=TARGET_DAYS,
        line={"color": theme.BAD, "width": 1, "dash": "dash"},
        annotation_text=f"{TARGET_DAYS}d target",
        annotation_position="top right",
    )
    scatter.add_vline(
        x=14,
        line={"color": theme.NEUTRAL, "width": 1, "dash": "dot"},
    )
    scatter.add_vline(
        x=30,
        line={"color": theme.NEUTRAL, "width": 1, "dash": "dot"},
    )
    scatter.add_vline(
        x=180,
        line={"color": theme.NEUTRAL, "width": 1, "dash": "dot"},
    )
    scatter.update_layout(
        title="Cover vs velocity (log scales)",
        xaxis={
            "title": "Cover days (log)",
            "type": "log",
            # Explicit bounds keep the chart readable: a few cells have cover
            # above 30,000 days, which would otherwise compress every point.
            "range": [-0.3, 4.6],
            "tickvals": [1, 10, 100, 1_000, 10_000],
            "ticktext": ["1", "10", "100", "1,000", "10,000"],
        },
        yaxis={
            "title": "90-day velocity, units/day (log)",
            "type": "log",
            "range": [-2.2, 2.5],
            "tickvals": [0.01, 0.1, 1, 10, 100],
            "ticktext": ["0.01", "0.1", "1", "10", "100"],
        },
    )
    theme.apply_plotly_style(scatter)
    st.plotly_chart(scatter, width="stretch", config={"displayModeBar": False})
    st.caption(
        "Excludes cells with no recent demand signal (no sales/transfers in the "
        "90-day window). Both axes are logarithmic; dashed lines mark 14, 30 and "
        "45 days, and 180 days marks overstock."
    )

st.divider()

# ----------------------------------------------------------- action tables -----
tabs = st.tabs(["Reorder priorities", "Overstock review"])

with tabs[0]:
    theme.section_header(f"Cells below the {TARGET_DAYS}-day target (top 25 by priority)")
    if below.empty:
        st.info("No cells below target in the current filter.")
    else:
        priority = {
            SIGNAL_ORDER[0]: 1,
            SIGNAL_ORDER[1]: 2,
            SIGNAL_ORDER[2]: 3,
        }
        reorder = below.copy()
        reorder["priority"] = reorder.signal.map(priority)
        reorder = reorder.sort_values(
            ["priority", "cover_days", "reorder_value_EGP"],
            ascending=[True, True, False],
        ).head(25)
        st.dataframe(
            reorder[
                [
                    "location_label",
                    "location_governorate_ar",
                    "stock_location_type",
                    "product_category",
                    "closing_units",
                    "velocity_90d",
                    "cover_days",
                    "reorder_units",
                    "reorder_value_EGP",
                    "stockout_risk_score",
                    "signal",
                    "action",
                ]
            ].round({"velocity_90d": 2, "cover_days": 1, "stockout_risk_score": 3}),
            hide_index=True,
            column_config={
                "location_label": st.column_config.TextColumn("Location"),
                "location_governorate_ar": st.column_config.TextColumn("Governorate"),
                "stock_location_type": st.column_config.TextColumn("Type", width="small"),
                "product_category": st.column_config.TextColumn("Category"),
                "closing_units": st.column_config.NumberColumn("Closing units", format="%.0f"),
                "velocity_90d": st.column_config.NumberColumn("Velocity (units/day)", format="%.2f"),
                "cover_days": st.column_config.NumberColumn("Cover days", format="%.1f"),
                "reorder_units": st.column_config.NumberColumn("Reorder units", format="%.0f"),
                "reorder_value_EGP": st.column_config.NumberColumn("Reorder value (EGP)", format="%.0f"),
                "stockout_risk_score": st.column_config.NumberColumn("Risk score", format="%.3f"),
                "signal": st.column_config.TextColumn("Signal"),
                "action": st.column_config.TextColumn("Action"),
            },
        )
        st.caption(
            "Reorder units = ceil(90-day velocity × 45 − closing units), floored "
            "at zero. This is a cover rule, not an economic order quantity: it does "
            "not use lead time, MOQ, shelf life or cash constraints."
        )

with tabs[1]:
    theme.section_header("Largest overstock cells (top 15 by closing value)")
    if overstock.empty:
        st.info("No overstock cells in the current filter.")
    else:
        over = overstock.sort_values("closing_stock_value", ascending=False).head(15)
        st.dataframe(
            over[
                [
                    "location_label",
                    "stock_location_type",
                    "product_category",
                    "closing_units",
                    "closing_stock_value",
                    "cover_days",
                    "stockout_risk_score",
                    "stock_status",
                ]
            ].round({"cover_days": 1, "stockout_risk_score": 3}),
            hide_index=True,
            column_config={
                "location_label": st.column_config.TextColumn("Location"),
                "stock_location_type": st.column_config.TextColumn("Type", width="small"),
                "product_category": st.column_config.TextColumn("Category"),
                "closing_units": st.column_config.NumberColumn("Closing units", format="%.0f"),
                "closing_stock_value": st.column_config.NumberColumn("Stock value (EGP)", format="%.0f"),
                "cover_days": st.column_config.NumberColumn("Cover days", format="%.1f"),
                "stockout_risk_score": st.column_config.NumberColumn("Risk score", format="%.3f"),
                "stock_status": st.column_config.TextColumn("Stock status"),
            },
        )

with st.expander("Rule definition and limits (audit A14)", expanded=False):
    st.markdown(
        "- **Snapshot**: `views.replenishment_signals` is the latest monthly stock "
        "snapshot (2026-10), not a live inventory feed. The sidebar reporting "
        "period does not change it; the page is a snapshot diagnosis.\n"
        "- **Velocity**: branches use units sold from `views.sales_enriched` over "
        "the 90 days ending 2026-10-18, divided by 90. Warehouses use outgoing "
        "transfer units from `raw.inventory_transfers` + items over the same "
        "window, because warehouses do not sell to customers.\n"
        "- **Cover**: closing units / daily velocity. A cell with no sales or "
        "transfers in the window gets `No demand signal`, not an infinite-cover "
        "reorder suggestion.\n"
        "- **Reorder rule**: `max(0, ceil(velocity × 45 − closing_units))`. The "
        "45-day target is a planning choice, not a fitted optimum. There is no "
        "lead-time, MOQ, seasonality, shelf-life or budget constraint in the rule.\n"
        "- **Grain limit**: the stock snapshot is location × category, not SKU. "
        "The reorder figure is a category-level signal; a buyer still has to "
        "translate it into SKUs. No supplier or open-PO netting is applied.\n"
        "- **Risk score** is the source `stockout_risk_score`; it is not used in "
        "the cover rule, to avoid double-counting."
    )
