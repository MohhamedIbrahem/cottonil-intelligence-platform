"""Inventory & Stock + Smart Replenishment (deck p.5-6 and p.18) - stock health.

US5 (tab 1) and S18 (tab 2) share one page since the 2026-10 UI refactor. The
same sidebar period scopes the trend, while snapshot KPIs always come from the
LATEST month (views.stock_latest = the last snapshot); audit A7 applies:
stock-to-sales scale is internally consistent, no adjustment. The transparent
45-day cover rule (A14) runs on that same snapshot; it is category-level, so
this cannot produce SKU purchase orders.

Each tab renders through its own function so the two blocks never share a
frame; page bodies are otherwise verbatim from the standalone pages.
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import data, global_filters, theme
from app.filters import DATA_END, selected_period

# One shared window for both tabs, read from the shell (the selector renders
# exactly once, in app/Home.py).
start, end, label, _ = selected_period()
# Aliases keep the moved Replenishment body verbatim from its standalone days.
_start, _end, _label, _mode = start, end, label, _

# Global cross-filters (App Shell v3): the governorate selection applies
# to the stock views through their own column name
# (location_governorate_ar). Channel/branch selections do not map onto
# stock locations, so they are not supported on this page.
_GF_SUPPORTED = {"governorate"}
_gf_loc_where, _gf_loc_params = global_filters.sales_where(
    _GF_SUPPORTED, columns={"governorate": "location_governorate_ar"}
)









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
    "Low (14-30d)": theme.ORANGE,
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
    WHERE 1 = 1
    """ + _gf_loc_where + """
    ORDER BY signal, cover_days
    """,
    _gf_loc_params,
)

def _render_stock() -> None:
    theme.page_header(
        "Inventory & Stock",
        f"Trend window: **{label}** · snapshot KPIs below use the **latest stock month** "
        f"(dataset ends {DATA_END.isoformat()}) · audit A7 scale policy",
        eyebrow="Operations",
        badges=('Latest snapshot',),
    )


    # ---------------------------------------------------------------- KPIs (T070) --
    latest_month = data.scalar("SELECT MAX(year_month) FROM views.stock_latest")
    snap = data.q(
        """
        SELECT SUM(closing_units) AS units, SUM(closing_stock_value) AS value_egp,
               COUNT(*) AS cells, COUNT(DISTINCT stock_location_id) AS locations
        FROM views.stock_latest
        WHERE 1 = 1
        """ + _gf_loc_where,
        _gf_loc_params,
    ).iloc[0]
    at_risk = data.scalar(
        "SELECT COUNT(*) FROM views.stock_latest WHERE stockout_risk_score >= 0.70"
        + _gf_loc_where,
        _gf_loc_params,
    ) or 0
    low_cells = data.scalar(
        "SELECT COUNT(*) FROM views.stock_latest WHERE stock_status = 'Low stock'"
        + _gf_loc_where,
        _gf_loc_params,
    ) or 0

    k_cols = st.columns(4)
    for col, (title, value, sub, tone) in zip(
        k_cols,
        [
            ("Stock units", theme.fmt_int(float(snap.units)), f"snapshot {latest_month}", "teal"),
            ("Stock value", theme.fmt_egp(float(snap.value_egp)), f"closing value, {latest_month}", "blue"),
            ("At-risk locations", theme.fmt_pct(int(at_risk) / max(int(snap.cells), 1)),
             f"risk \u22650.70 · {at_risk} of {int(snap.cells)} location×category cells", "red"),
            ("Low-stock cells", f"{int(low_cells)}", "view bucket policy (risk \u22650.60)", "amber"),
        ],
        strict=True,
    ):
        with col:
            theme.kpi_card(title, value, sub=sub, tone=tone)

    # Insights-first strip (App Shell v3): from the snapshot KPIs above
    # plus the single highest-risk cell — one extra scalar-grade query.
    _top_risk = data.q(
        "SELECT location_label, product_category, stockout_risk_score "
        "FROM views.stock_latest WHERE 1 = 1"
        + _gf_loc_where
        + " ORDER BY stockout_risk_score DESC LIMIT 1",
        _gf_loc_params,
    )
    theme.insight_strip([
        {
            "icon": "\u26A0\uFE0F", "label": "Stockout risk",
            "value": f"{int(at_risk)} at-risk cells",
            "sub": f"risk \u22650.70 · {theme.fmt_pct(int(at_risk) / max(int(snap.cells), 1))} of the latest snapshot",
            "tone": "bad" if int(at_risk) else "good",
        },
        {
            "icon": "\U0001F4E6", "label": "Low stock",
            "value": f"{int(low_cells)} low-stock cells",
            "sub": "view bucket policy (risk \u22650.60)",
            "tone": "warn" if int(low_cells) else "good",
        },
        {
            "icon": "\U0001F4CD", "label": "Highest-risk cell",
            "value": (f"{_top_risk.iloc[0].location_label} · {_top_risk.iloc[0].product_category}"
                      if len(_top_risk) else "—"),
            "sub": (f"stockout risk {float(_top_risk.iloc[0].stockout_risk_score):.2f} in {latest_month}"
                    if len(_top_risk) else "no snapshot rows"),
            "tone": "bad" if len(_top_risk) and float(_top_risk.iloc[0].stockout_risk_score) >= 0.70 else "neutral",
        },
    ])

    st.divider()

    # ------------------------------------------------------------ trend (T071) --
    ym_start = pd.Period(start, freq="M").strftime("%Y-%m")
    ym_end = pd.Period(end, freq="M").strftime("%Y-%m")
    trend = data.q(
        """
        SELECT year_month, UPPER(stock_location_type) AS loc_type,
               SUM(closing_units) AS units, SUM(closing_stock_value) AS value_egp
        FROM views.stock_monthly
        WHERE year_month BETWEEN ? AND ?
        """ + _gf_loc_where + """
        GROUP BY year_month, UPPER(stock_location_type)
        ORDER BY year_month
        """,
        (ym_start, ym_end) + _gf_loc_params,
    )
    val_fig = go.Figure()
    for loc_type, color in zip(("BRANCH", "WAREHOUSE"), (theme.ACCENT, theme.ACCENT_2), strict=False):
        sub = trend[trend.loc_type == loc_type]
        if sub.empty:
            continue
        val_fig.add_trace(go.Scatter(
            x=pd.to_datetime(sub.year_month + "-01"), y=sub.value_egp, name=loc_type.title(),
            stackgroup="value", line={"width": 1.5, "color": color},
            hovertemplate="%{x|%b %Y}: EGP %{y:,.0f}<extra></extra>",
        ))
    val_fig.update_layout(title="Closing stock value by location type")
    theme.apply_plotly_style(val_fig)
    val_fig.update_xaxes(tickformat="%b %Y")

    u_fig = go.Figure()
    for loc_type, color in zip(("BRANCH", "WAREHOUSE"), (theme.ACCENT, theme.ACCENT_2), strict=False):
        sub = trend[trend.loc_type == loc_type]
        if sub.empty:
            continue
        u_fig.add_trace(go.Scatter(
            x=pd.to_datetime(sub.year_month + "-01"), y=sub.units, name=loc_type.title(),
            stackgroup="units", line={"width": 1.5, "color": color},
            hovertemplate="%{x|%b %Y}: %{y:,.0f} units<extra></extra>",
        ))
    u_fig.update_layout(title="Closing stock units by location type")
    theme.apply_plotly_style(u_fig)
    u_fig.update_xaxes(tickformat="%b %Y")

    t_col, u_col = st.columns(2)
    with t_col:
        st.plotly_chart(val_fig, width="stretch", config={"displayModeBar": False})
    with u_col:
        st.plotly_chart(u_fig, width="stretch", config={"displayModeBar": False})

    # ------------------------------------------- category mix & status (T072) --
    cat_mix = data.q(
        """
        SELECT product_category AS category, SUM(closing_stock_value) AS value_egp,
               SUM(closing_units) AS units
        FROM views.stock_latest
        WHERE 1 = 1
        """ + _gf_loc_where + """
        GROUP BY 1 ORDER BY 2 DESC
        """,
        _gf_loc_params,
    )
    if len(cat_mix) > 8:
        head8, tail = cat_mix.iloc[:8].copy(), cat_mix.iloc[8:].copy()
        head8.loc[len(head8)] = ["Other", tail.value_egp.sum(), tail.units.sum()]
        cat_plot = head8
    else:
        cat_plot = cat_mix

    status = data.q(
        """
        SELECT stock_status AS status, COUNT(*) AS cells,
               SUM(closing_stock_value) AS value_egp
        FROM views.stock_latest
        WHERE 1 = 1
        """ + _gf_loc_where + """
        GROUP BY 1 ORDER BY 2 DESC
        """,
        _gf_loc_params,
    )

    cat_fig = go.Figure(go.Pie(
        hole=0.56, labels=cat_plot.category, values=cat_plot.value_egp,
        marker={"colors": theme.COLORS}, textinfo="percent",
        customdata=cat_plot.units,
        hovertemplate="%{label}: EGP %{value:,.0f} (%{percent}) \u00b7 %{customdata:,.0f} units<extra></extra>",
    ))
    cat_fig.update_layout(title=f"Stock value mix by category — {latest_month}")
    theme.apply_plotly_style(cat_fig)

    status_fig = go.Figure(go.Pie(
        hole=0.56, labels=status.status, values=status.value_egp,
        marker={"colors": [theme.WARN, theme.ACCENT_2, theme.ACCENT], "line": {"color": theme.CARD, "width": 2}},
        textinfo="label+percent",
        customdata=status.cells,
        hovertemplate="%{label}: EGP %{value:,.0f} (%{percent}) \u00b7 %{customdata:,} cells<extra></extra>",
    ))
    status_fig.update_layout(title=f"Stock status buckets — {latest_month}")
    theme.apply_plotly_style(status_fig)

    m_col, s_col = st.columns(2)
    with m_col:
        st.plotly_chart(cat_fig, width="stretch", config={"displayModeBar": False})
    with s_col:
        st.plotly_chart(status_fig, width="stretch", config={"displayModeBar": False})

    # ------------------------------------------------- risk alerts table (T073) --
    alerts = data.q(
        """
        SELECT location_label AS location, stock_location_type AS type,
               location_governorate_ar AS governorate, product_category AS category,
               closing_units AS units, closing_stock_value AS value_egp,
               stockout_risk_score AS risk
        FROM views.stock_latest
        WHERE 1 = 1
        """ + _gf_loc_where + """
        ORDER BY risk DESC LIMIT 10
        """,
        _gf_loc_params,
    )


    def _risk_style(v: float) -> str:
        if v >= 0.70:
            return f"color: {theme.BAD}; font-weight: 600;"
        if v >= 0.60:
            return f"color: {theme.WARN}; font-weight: 600;"
        return f"color: {theme.TEXT_MUTED};"


    theme.section_header(f"Top-10 stockout-risk alerts — {latest_month}")
    st.dataframe(
        alerts.style.map(_risk_style, subset=["risk"]),
        hide_index=True,
        column_config={
            "location": st.column_config.TextColumn("Location"),
            "type": st.column_config.TextColumn("Type", width="small"),
            "governorate": st.column_config.TextColumn("Governorate", width="small"),
            "category": st.column_config.TextColumn("Category"),
            "units": st.column_config.NumberColumn("Units", format="%.0f"),
            "value_egp": st.column_config.NumberColumn("Value (EGP)", format="%.0f"),
            "risk": st.column_config.NumberColumn("Stockout risk", format="%.2f"),
        },
    )

    # -------------------------------------------------------- notes (T074) --
    with st.expander("Data notes - definitions & caveats for this page", expanded=False):
        st.markdown(
            f"""
    - **Grain**: `monthly_stock` is month × location × category ({int(snap.cells)} cells in the
      latest snapshot across {int(snap.locations)} locations = 80 branches + 12 warehouses).
      Stock is tracked per **category**, not per SKU.
    - **Two thresholds, both from real policy**: the "% locations at risk" KPI counts cells
      with `stockout_risk_score \u2265 0.70` (deck alert line, task definition); the 'Low stock'
      bucket in `views.stock_status` triggers at \u2265 0.60. Both are labeled wherever used.
    - **Status buckets** (view policy): risk \u2265 0.60 \u2192 Low stock; else top-decile closing
      units within (month, category) \u2192 Overstock; else In stock.
    - **A7 scale**: closing stock value (~{theme.fmt_egp(float(snap.value_egp))}) sits above
      yearly net sales — a stock-holding retailer's normal profile; no adjustment applied.
      Use stock analytics as absolute levels, never as a revenue ratio.
    - **Trend** follows the sidebar period (month-level, so the boundary month is full).
      Snapshot KPIs always use `{latest_month}` regardless of the selector — they describe
      the dataset's last state, not the selected window.
    - **Data through {DATA_END.isoformat()}**.
    """
        )

def _render_replenishment() -> None:

    f_loc, f_cat, f_sig = st.columns(3)

    with f_loc:
        locations = st.selectbox(
            "Location type", ["All locations", "Branch", "Warehouse"],
        )

    with f_cat:
        categories = sorted(cells.product_category.unique())
        category = st.selectbox("Category", ["All categories", *categories])

    with f_sig:
        signal_filter = st.selectbox("Signal", ["All signals", *SIGNAL_ORDER])

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
            tone="amber",
        )
    with cards[1]:
        theme.kpi_card(
            "Critical (<14 days)",
            theme.fmt_int(float(len(critical))),
            sub="reorder now · lowest cover in the snapshot",
            tone="red",
        )
    with cards[2]:
        theme.kpi_card(
            "Suggested reorder units",
            theme.fmt_int(float(below.reorder_units.sum())),
            sub=f"to reach {TARGET_DAYS} days of cover · {len(below):,} cells",
            tone="teal",
        )
    with cards[3]:
        theme.kpi_card(
            "Overstock value",
            theme.fmt_egp(float(overstock.closing_stock_value.sum())),
            sub=f"{len(overstock):,} overstock cells · no auto-reorder",
            tone="rose",
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

global_filters.render_filter_bar(_GF_SUPPORTED)

stock_tab, repl_tab = st.tabs(["Inventory & Stock", "Replenishment"])

with stock_tab:
    _render_stock()

with repl_tab:
    _render_replenishment()
