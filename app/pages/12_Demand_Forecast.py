"""Demand Forecasting (S7) - monthly demand baseline with a backtested band.

The model is a Holt-Winters exponential smoother (additive damped trend,
multiplicative seasonality) fitted on complete months only. 2026-10 is partial
and excluded. The page reports rolling-origin backtest error next to the
forecast so the uncertainty is visible, not hidden.
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import plotly.graph_objects as go
import streamlit as st

from app import analytics, data, theme
from app.filters import DATA_END, selected_period

start, end, label, _ = selected_period()

ALL_CATEGORIES = "All categories"
MEASURES = {
    "Units": ("units", "units", theme.fmt_int),
    "Net sales (EGP)": ("net_sales", "EGP net sales", theme.fmt_egp),
}
measure_label = st.sidebar.radio("Forecast measure", list(MEASURES), index=0)
categories = data.q(
    "SELECT DISTINCT category_en FROM views.demand_monthly ORDER BY 1"
).iloc[:, 0].tolist()
category = st.sidebar.selectbox("Category", [ALL_CATEGORIES, *categories])


@st.cache_data(ttl=600, show_spinner="Fitting demand model…")
def _forecast(category_name: str, measure: str) -> dict:
    value_col = MEASURES[measure][0]
    category_sql = "" if category_name == ALL_CATEGORIES else " AND category_en = ?"
    params: tuple = () if category_name == ALL_CATEGORIES else (category_name,)
    frame = data.q(
        f"""
        SELECT ym, SUM({value_col}) AS value
        FROM views.demand_monthly
        WHERE is_complete_month{category_sql}
        GROUP BY 1
        ORDER BY 1
        """,
        params,
    )
    return analytics.forecast_demand(frame, value_col="value")


result = _forecast(category, measure_label)
history = result["history"]
forecast = result["forecast"]
backtest = result["backtest"]
seasonal = result["seasonal_index"]
metrics = result["metrics"]
value_col, value_title, formatter = MEASURES[measure_label]

last = history.iloc[-1]
forecast_total = float(forecast["forecast"].sum())
prior_same_months = float(history["actual"].iloc[-12:-6].sum())
forecast_growth = forecast_total / prior_same_months - 1 if prior_same_months else 0.0
band_pct = metrics["band_pct"]

theme.page_header(
    "Demand Forecast",
    f"Scope: **{category}** · measure: **{value_title}** · chart window **{label}** · "
    f"model fitted on {metrics['train_months']} complete months through "
    f"**2026-09** · partial 2026-10 excluded · data through {DATA_END.isoformat()}",
    eyebrow="Planning",
    badges=('Backtested baseline',),
)

cards = st.columns(4)
with cards[0]:
    theme.kpi_card(
        f"Last complete month · {last['ym']}",
        formatter(float(last["actual"])),
        sub="actual demand · October 2026 is partial and excluded",
        tone="teal",
    )
with cards[1]:
    theme.kpi_card(
        "Next 6-month forecast",
        formatter(forecast_total),
        delta=f"{forecast_growth:+.1%} vs the same 6 months a year earlier",
        delta_up=forecast_growth >= 0,
        delta_good=forecast_growth >= 0,
        sub=f"{forecast['ym'].iloc[0]} – {forecast['ym'].iloc[-1]} · sum of monthly forecast",
        tone="blue",
    )
with cards[2]:
    theme.kpi_card(
        "Latest 12-month holdout WAPE",
        f"{metrics['wape_latest']:.1%}",
        sub=(
            f"mean {metrics['wape_mean']:.1%} across "
            f"{metrics['backtest_windows']} rolling origins · lower is better"
        ),
        tone="amber",
    )
with cards[3]:
    theme.kpi_card(
        "Model",
        "Holt-Winters",
        sub=f"additive damped trend · multiplicative season · ±{band_pct:.1%} planning band",
        tone="violet",
    )

# Insights-first strip (App Shell v3): from the forecast metrics above.
theme.insight_strip([
    {
        "icon": "\U0001F52E", "label": "Next 6 months",
        "value": f"{forecast_growth:+.1%} vs a year earlier",
        "sub": "sum of the monthly forecast vs the same 6 months last year",
        "tone": "good" if forecast_growth >= 0 else "warn",
    },
    {
        "icon": "\U0001F3AF", "label": "Holdout WAPE",
        "value": f"{metrics['wape_latest']:.1%}",
        "sub": f"latest 12-month holdout · mean {metrics['wape_mean']:.1%} across {metrics['backtest_windows']} origins · lower is better",
        "tone": "good" if metrics["wape_latest"] <= 0.25 else "warn",
    },
    {
        "icon": "\U0001F4C5", "label": "Last complete month",
        "value": formatter(float(last["actual"])),
        "sub": f"actual demand in {last['ym']} · partial month excluded",
        "tone": "neutral",
    },
])

st.divider()

# --------------------------------------------------------------- forecast plot --
history_view = history[history["ym"] >= start.strftime("%Y-%m")]
if len(history_view) < 24:
    history_view = history.tail(24)

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=history_view["ym"],
        y=history_view["actual"],
        mode="lines",
        name="Actual",
        line={"color": theme.ACCENT, "width": 2.5},
    )
)
fig.add_trace(
    go.Scatter(
        x=history_view["ym"],
        y=history_view["fitted"],
        mode="lines",
        name="Model fit",
        line={"color": theme.TEXT_MUTED, "width": 1, "dash": "dot"},
        hovertemplate="%{y:,.0f}<extra>model fit</extra>",
    )
)
fig.add_trace(
    go.Scatter(
        x=forecast["ym"],
        y=forecast["hi"],
        mode="lines",
        line={"width": 0},
        showlegend=False,
        hoverinfo="skip",
    )
)
fig.add_trace(
    go.Scatter(
        x=forecast["ym"],
        y=forecast["lo"],
        mode="lines",
        fill="tonexty",
        fillcolor=theme.ACCENT_SOFT,
        line={"width": 0},
        name=f"Planning band (±{band_pct:.1%})",
        hoverinfo="skip",
    )
)
fig.add_trace(
    go.Scatter(
        x=forecast["ym"],
        y=forecast["forecast"],
        mode="lines+markers",
        name="Forecast",
        line={"color": theme.ACCENT_2, "width": 2.5},
        marker={"size": 7},
    )
)
fig.add_vline(
    x=history["ym"].iloc[-1],
    line={"color": theme.NEUTRAL, "width": 1, "dash": "dash"},
)
fig.update_layout(
    title=f"{value_title} — actual, fitted and 6-month forecast",
    yaxis_title=value_title,
    hovermode="x unified",
)
theme.apply_plotly_style(fig)
st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
st.caption(
    "The shaded band is the empirical 80th-percentile absolute error from the rolling "
    "backtests — a planning range, not a statistical confidence interval. The dashed "
    "line marks the last complete month (Sep 2026)."
)

st.divider()

# ------------------------------------------------- seasonality + backtest tables --
left, right = st.columns((3, 2))

with left:
    theme.section_header("Seasonal shape")
    season_fig = go.Figure(
        go.Bar(
            x=seasonal["month_name"],
            y=seasonal["index"],
            marker_color=[
                theme.ACCENT if value >= 1 else theme.ACCENT_2_SOFT
                for value in seasonal["index"]
            ],
            hovertemplate="%{x}: index %{y:.2f}<extra></extra>",
        )
    )
    season_fig.add_hline(
        y=1.0,
        line={"color": theme.TEXT_MUTED, "width": 1, "dash": "dot"},
        annotation_text="average month = 1.0",
        annotation_position="top left",
    )
    season_fig.update_layout(
        yaxis_title="Seasonal index",
        xaxis_title="Calendar month",
        showlegend=False,
    )
    theme.apply_plotly_style(season_fig)
    st.plotly_chart(season_fig, width="stretch", config={"displayModeBar": False})
    st.caption(
        "Index = month's average ratio to a centred 12-month moving average, "
        "normalised to 1.0. This is descriptive seasonality, not a causal effect."
    )

with right:
    theme.section_header("Rolling-origin backtest")
    backtest_view = backtest.rename(
        columns={
            "test_start": "Holdout start",
            "test_end": "Holdout end",
            "train_months": "Train months",
            "wape": "WAPE (%)",
            "mae": "MAE",
            "bias": "Bias (%)",
        }
    )
    backtest_view["WAPE (%)"] = backtest_view["WAPE (%)"] * 100
    backtest_view["Bias (%)"] = backtest_view["Bias (%)"] * 100
    st.dataframe(
        backtest_view,
        hide_index=True,
        column_config={
            "Holdout start": st.column_config.TextColumn("Holdout start", width="small"),
            "Holdout end": st.column_config.TextColumn("Holdout end", width="small"),
            "Train months": st.column_config.NumberColumn("Train months", format="%.0f"),
            "WAPE (%)": st.column_config.NumberColumn("WAPE (%)", format="%.1f"),
            "MAE": st.column_config.NumberColumn("MAE", format="%.0f"),
            "Bias (%)": st.column_config.NumberColumn("Bias (%)", format="%.1f"),
        },
    )
    st.caption(
        "Each origin trains on data before the holdout and forecasts the next 12 "
        "months. Bias = sum(predicted − actual) / sum(actual); positive means "
        "the model over-forecast the holdout."
    )

with st.expander("Model definition, exclusions and limitations (audit A15)", expanded=False):
    st.markdown(
        f"- **Model**: {metrics['model']}, fitted with `statsmodels` "
        f"({metrics['train_months']} complete months).\n"
        f"- **Excluded month**: 2026-10 is partial (dataset ends 2026-10-18), "
        "so it is not used for fitting or backtesting.\n"
        f"- **Backtest**: {metrics['backtest_windows']} rolling 12-month origins; "
        f"latest holdout WAPE **{metrics['wape_latest']:.1%}**, mean "
        f"**{metrics['wape_mean']:.1%}**. The latest holdout is the most relevant "
        "read, but it is still a small sample.\n"
        f"- **Planning band**: ±{band_pct:.1%}, the 80th percentile of absolute "
        "percentage errors across all backtest months. It is not a statistical "
        "confidence interval and does not widen with horizon.\n"
        "- **No causal drivers**: price, promotion, stockouts, weather, competitor "
        "actions and distribution changes are not in the model. It is a baseline, "
        "not a commitment.\n"
        "- **Grain**: one forecast per category series (or the company total). "
        "SKU-level forecasts are not produced because the stock snapshot and "
        "assortment churn make that unstable."
    )
