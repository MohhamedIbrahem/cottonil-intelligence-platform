"""Design system for the Cottonil app — Light Pro theme.

Professional light theme built on one palette:
deep Cottonil blue as the brand primary, darkened chart colors so every
line / label stays readable on white, warm-neutral surfaces, and
semantic colors darkened for text use (yellow -> amber, etc).

Backward compatibility: the old constant names (NAVY_BG, NAVY_CARD,
NAVY_CARD_2) are kept as aliases to the new light surfaces so existing
pages keep working. New code should use BG / SURFACE / SURFACE_2.
"""
from __future__ import annotations
import streamlit as st

PRIMARY = "#0F4C75"
PRIMARY_DARK = "#0B3553"
ACCENT = "#1B7AC2"
ACCENT_2 = "#0284C7"
BG = "#F7F8FA"
SURFACE = "#FFFFFF"
SURFACE_2 = "#EEF2F7"
BORDER = "#E2E8F0"
TEXT = "#0F172A"
TEXT_MUTED = "#64748B"
TEXT_ON_COLOR = "#FFFFFF"
GOOD = "#159947"
BAD = "#DC3A3A"
WARN = "#D97706"
COLORS = ["#0F4C75","#1B7AC2","#0E9F8A","#E9A23B","#7C5CFC","#E85D75","#22A06B","#64748B"]
NAVY_BG = BG
NAVY_CARD = SURFACE
NAVY_CARD_2 = SURFACE

CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{ background-color: {BG}; }}
[data-testid="stSidebar"] {{ background-color: {SURFACE}; border-right: 1px solid {BORDER}; }}
[data-testid="stHeader"] {{ background-color: transparent; }}
.block-container {{ padding-top: 2rem; padding-bottom: 2rem; max-width: 1440px; }}
footer {{ visibility: hidden; }}
hr {{ border-color: {BORDER}; }}
h1 {{ color: {PRIMARY_DARK}; font-weight: 800; letter-spacing: -0.02em; }}
h2, h3, h4 {{ color: {TEXT}; font-weight: 700; letter-spacing: -0.01em; }}
.cottonil-kpi {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 16px;
    padding: 16px 18px 14px 18px; color: {TEXT}; height: 100%;
    box-shadow: 0 1px 2px rgba(15,23,42,.05), 0 8px 24px rgba(15,23,42,.04);
    transition: box-shadow .18s ease, transform .18s ease, border-color .18s ease;
}}
.cottonil-kpi:hover {{ border-color: #CBD8E6; box-shadow: 0 2px 4px rgba(15,23,42,.06), 0 12px 32px rgba(15,76,117,.08); transform: translateY(-1px); }}
.cottonil-kpi .cpi-title {{ font-size: 0.76rem; letter-spacing: 0.08em; text-transform: uppercase; color: {TEXT_MUTED}; margin: 0 0 4px 0; font-weight: 600; display: flex; align-items: center; }}
.cottonil-kpi .cpi-value {{ font-size: 1.85rem; font-weight: 800; line-height: 1.15; color: {TEXT}; }}
.cottonil-kpi .cpi-delta {{ margin-top: 2px; font-weight: 700; font-size: 0.85rem; }}
.cottonil-kpi .cpi-sub {{ color: {TEXT_MUTED}; font-size: 0.72rem; line-height: 1.45; }}
.badge-good {{ color: {GOOD}; }} .badge-bad {{ color: {BAD}; }} .badge-warn {{ color: {WARN}; }}
[data-testid="stMetric"] > div {{ background: transparent; }}
.stButton > button, .stDownloadButton > button {{ background-color: {PRIMARY}; color: #fff; border: 1px solid {PRIMARY}; border-radius: 10px; font-weight: 600; }}
.stButton > button:hover, .stDownloadButton > button:hover {{ background-color: {PRIMARY_DARK}; border-color: {PRIMARY_DARK}; color: #fff; }}
div[data-baseweb="select"] > div, .stTextInput input, .stNumberInput input {{ border-color: {BORDER}; border-radius: 10px; background-color: {SURFACE}; }}
[data-testid="stExpander"] {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
[data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 12px; overflow: hidden; }}
section[data-testid="stSidebar"] .stSelectbox, section[data-testid="stSidebar"] .stRadio {{ color: {TEXT}; }}
[data-testid="stChatMessage"] {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; }}
</style>
"""

def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)

def kpi_card(title: str, value: str, *, delta: str | None = None, delta_up: bool = True, delta_good: bool = True, sub: str | None = None) -> None:
    arrow = "\u25b2" if delta_up else "\u25bc"
    delta_class = "badge-good" if delta_good else "badge-bad"
    delta_html = f'<div class="cpi-delta {delta_class}">{arrow} {delta}</div>' if delta else ""
    sub_row = f'<div class="cpi-sub">{sub}</div>' if sub else ""
    html = f'<div class="cottonil-kpi"><div class="cpi-title">{title}</div><div class="cpi-value">{value}</div>{delta_html}{sub_row}</div>'
    st.markdown(html, unsafe_allow_html=True)

def apply_plotly_style(fig) -> None:
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": TEXT_MUTED, "family": "Inter, Segoe UI, sans-serif", "size": 12},
        title={"font": {"color": TEXT, "size": 14}},
        margin={"l": 10, "r": 10, "t": 36, "b": 10},
        legend={"orientation": "h", "y": -0.15}, hovermode="x unified", colorway=COLORS,
    )
    fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER)
    fig.update_xaxes(gridcolor="rgba(226,232,240,0.6)", zerolinecolor=BORDER)

def _compact(value: float) -> tuple[float, str]:
    magnitude = abs(value)
    if magnitude >= 1_000_000_000: return value / 1_000_000_000, "B"
    if magnitude >= 1_000_000: return value / 1_000_000, "M"
    if magnitude >= 1_000: return value / 1_000, "K"
    return value, ""

def fmt_egp(value: float) -> str:
    number, suffix = _compact(value)
    return f"EGP {number:,.1f}{suffix}"

def fmt_int(value: float) -> str:
    number, suffix = _compact(value)
    if suffix: return f"{number:,.1f}{suffix}"
    return f"{number:,.0f}"

def fmt_pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:,.{digits}f}%"
