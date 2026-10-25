"""Design system for the Cottonil app (deck p1 visual language).

Navy cards, blue accents, green/red delta badges per Constitution II
(the deck is the design language only - numbers always come from the dataset).
"""

from __future__ import annotations

import streamlit as st

# Palette (deck-matched)
NAVY_BG = "#0B1526"
NAVY_CARD = "#13234C"
NAVY_CARD_2 = "#0F1D3D"
ACCENT = "#2F80ED"
ACCENT_2 = "#56CCF2"
TEXT = "#E8EEF7"
TEXT_MUTED = "#8FA6C9"
GOOD = "#2ECC71"
BAD = "#EB5757"
WARN = "#F2C94C"

CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{ background-color: {NAVY_BG}; }}
[data-testid="stSidebar"] {{ background-color: {NAVY_CARD_2}; }}
[data-testid="stMetric"] > div {{ background: transparent; }}

.cottonil-kpi {{
    background: linear-gradient(145deg, {NAVY_CARD} 0%, {NAVY_CARD_2} 100%);
    border: 1px solid rgba(86, 146, 255, 0.25);
    border-radius: 14px;
    padding: 14px 18px 12px 18px;
    color: {TEXT};
    height: 100%;
}}
.cottonil-kpi .cpi-title {{
    font-size: 0.76rem; letter-spacing: 0.08em; text-transform: uppercase;
    color: {TEXT_MUTED}; margin: 0 0 4px 0; display: flex; align-items: center;
}}
.cottonil-kpi .cpi-value {{ font-size: 1.85rem; font-weight: 700; line-height: 1.15; }}
.cottonil-kpi .cpi-delta {{ margin-top: 2px; font-weight: 700; font-size: 0.85rem; }}
.cottonil-kpi .cpi-sub {{ color: {TEXT_MUTED}; font-size: 0.72rem; }}
.badge-good {{ color: {GOOD}; }}
.badge-bad {{ color: {BAD}; }}
.badge-warn {{ color: {WARN}; }}

section[data-testid="stSidebar"] .stSelectbox, section[data-testid="stSidebar"] .stRadio {{
    color: {TEXT};
}}
footer {{ visibility: hidden; }}
[data-testid="stHeader"] {{ background-color: transparent; }}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def kpi_card(
    title: str,
    value: str,
    *,
    delta: str | None = None,
    delta_up: bool = True,
    delta_good: bool = True,
    sub: str | None = None,
) -> None:
    """Render a deck-style KPI tile (title, big value, colored delta, sub-line)."""
    arrow = "\u25b2" if delta_up else "\u25bc"
    delta_class = "badge-good" if delta_good else "badge-bad"
    delta_html = (
        f'<div class="cpi-delta {delta_class}">{arrow} {delta}</div>' if delta else ""
    )
    sub_row = f'<div class="cpi-sub">{sub}</div>' if sub else ""
    html = (
        f'<div class="cottonil-kpi">'
        f'<div class="cpi-title">{title}</div>'
        f'<div class="cpi-value">{value}</div>'
        f"{delta_html}{sub_row}"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def apply_plotly_style(fig) -> None:
    """Uniform dark template for every chart in the app."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": TEXT_MUTED, "family": "Segoe UI, sans-serif"},
        margin={"l": 10, "r": 10, "t": 28, "b": 10},
        legend={"orientation": "h", "y": -0.15},
        hovermode="x unified",
        colorway=[ACCENT_2, ACCENT, WARN, GOOD, BAD, "#9B51E0", "#F2994A"],
    )
    fig.update_yaxes(gridcolor="rgba(143,166,201,0.15)")
    fig.update_xaxes(gridcolor="rgba(143,166,201,0.08)")


def _compact(value: float) -> tuple[float, str]:
    magnitude = abs(value)
    if magnitude >= 1_000_000_000:  # billion
        return value / 1_000_000_000, "B"
    if magnitude >= 1_000_000:  # million
        return value / 1_000_000, "M"
    if magnitude >= 1_000:
        return value / 1_000, "K"
    return value, ""


def fmt_egp(value: float) -> str:
    """EGP 148.8M style (compact, deck-like)."""
    number, suffix = _compact(value)
    return f"EGP {number:,.1f}{suffix}"


def fmt_int(value: float) -> str:
    number, suffix = _compact(value)
    if suffix:
        return f"{number:,.1f}{suffix}"
    return f"{number:,.0f}"


def fmt_pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:,.{digits}f}%"
