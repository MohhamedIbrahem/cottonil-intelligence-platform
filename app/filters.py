"""Shared reporting-period selector (deck p2 'Jan 2024 - Dec 2024' control).

Constitution: default = Last 12 months ending at the dataset's last date
(Oct 2025-19 -> Oct 2026-18 per audit A5). Calendar-year and All-time modes
are selectable; the deck's 'Jan 2024 - Dec 2024' is reachable via Calendar year.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from pipeline import config

MODE_LAST_12M = "Last 12 months"
MODE_YEAR = "Calendar year"
MODE_ALL = "All time"
MODES = (MODE_LAST_12M, MODE_YEAR, MODE_ALL)

DATA_START = date(2018, 10, 19)  # first transaction date in the dataset
DATA_END = date.fromisoformat(config.DATA_END_DATE)
AVAILABLE_YEARS = list(range(DATA_END.year, DATA_START.year - 1, -1))


def render_period_selector() -> tuple[date, date, str, str]:
    """Draw the sidebar control; return (start, end, label, mode) - end inclusive."""
    mode = st.sidebar.radio("Reporting period", MODES, index=0)

    if mode == MODE_ALL:
        return DATA_START, DATA_END, f"All time ({DATA_START.year}\u2013{DATA_END.year})", mode

    if mode == MODE_YEAR:
        year = st.sidebar.selectbox("Calendar year", AVAILABLE_YEARS, index=0)
        start = date(year, 1, 1)
        end = min(date(year, 12, 31), DATA_END)
        label = f"{start.strftime('%b %Y')} \u2013 {end.strftime('%b %Y')}"
        return start, end, label, mode

    start = DATA_END - timedelta(days=364)
    return (
        start,
        DATA_END,
        f"Last 12 months ({start.strftime('%b %Y')} \u2013 {DATA_END.strftime('%b %Y')})",
        mode,
    )


def previous_period(start: date, end: date, mode: str) -> tuple[date, date] | None:
    """The comparison window for YoY deltas.

    Same calendar-span one year earlier (so a partial current year, capped at
    the dataset end, is compared against the same span of the previous year -
    Constitutional honesty over raw percentage). Returns None for All time
    (there is no like-for-like earlier window in the dataset).
    """
    if mode == MODE_ALL:
        return None

    def shift_one_year(d: date) -> date:
        try:
            return date(d.year - 1, d.month, d.day)
        except ValueError:  # Feb 29
            return date(d.year - 1, d.month, 28)

    return shift_one_year(start), shift_one_year(end)


def window_label(window: tuple[date, date] | None, empty: str = "n/a") -> str:
    """Render a comparison window as 'Oct 2025 – Oct 2026'."""
    if not window:
        return empty
    start, end = window
    return f"{start:%b %Y} \u2013 {end:%b %Y}"


def delta_label(
    current: float,
    previous: float | None,
    *,
    label: str,
    lower_is_better: bool = False,
) -> tuple[str, bool, bool]:
    """Return (delta text, arrow up, is good) against a comparison window."""
    if previous is None or pd.isna(previous) or previous == 0:
        return "n/a", True, False
    pct = float(current) / float(previous) - 1.0
    up = pct >= 0
    return f"{pct:+.1%} vs {label}", up, up == (not lower_is_better)
