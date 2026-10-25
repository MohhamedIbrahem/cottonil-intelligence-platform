"""Shared reporting-period selector (deck p2 'Jan 2024 - Dec 2024' control).

Constitution: default = Last 12 months ending at the dataset's last date
(Oct 2025-19 -> Oct 2026-18 per audit A5). Calendar-year and All-time modes
are selectable; the deck's 'Jan 2024 - Dec 2024' is reachable via Calendar year.
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from pipeline import config

MODE_LAST_12M = "Last 12 months"
MODE_YEAR = "Calendar year"
MODE_ALL = "All time"
MODES = (MODE_LAST_12M, MODE_YEAR, MODE_ALL)

DATA_START = date(2018, 10, 19)  # first transaction date in the dataset
DATA_END = date.fromisoformat(config.DATA_END_DATE)
AVAILABLE_YEARS = list(range(DATA_END.year, DATA_START.year - 1, -1))


def render_period_selector() -> tuple[date, date, str]:
    """Draw the sidebar control; return (start, end, label) - end is inclusive."""
    mode = st.sidebar.radio("Reporting period", MODES, index=0)

    if mode == MODE_ALL:
        return DATA_START, DATA_END, f"All time ({DATA_START.year}\u2013{DATA_END.year})"

    if mode == MODE_YEAR:
        year = st.sidebar.selectbox("Calendar year", AVAILABLE_YEARS, index=0)
        start = date(year, 1, 1)
        end = min(date(year, 12, 31), DATA_END)
        label = f"{start.strftime('%b %Y')} \u2013 {end.strftime('%b %Y')}"
        return start, end, label

    start = DATA_END - timedelta(days=364)
    return (
        start,
        DATA_END,
        f"Last 12 months ({start.strftime('%b %Y')} \u2013 {DATA_END.strftime('%b %Y')})",
    )


def period_params(start: date, end: date) -> tuple[date, date]:
    return start, end


PERIOD_WHERE = "BETWEEN ? AND ?"
