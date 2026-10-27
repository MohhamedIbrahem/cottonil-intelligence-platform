"""Design system for the Cottonil Intelligence Platform (light theme).

Presentation only: tokens (brand navy + coordinated blue/teal/violet/amber/
rose/green/red chart family), typography, the brand-navy sidebar, cards, KPI
tone strips, status chips, page headers and a single Plotly template. Every
number on screen still comes from the curated views; this module never queries
or calculates business metrics. PALETTE.md documents these exact tokens.
"""

from __future__ import annotations

import html
import re
from collections.abc import Sequence
from contextlib import contextmanager as _contextmanager

import streamlit as st

# ------------------------------------------------------------------ tokens --
# Modern Analytics light palette. Contrast on white:
#   TEXT 15.9:1 | NAVY 11.4:1 | MUTED 4.8:1 | ACCENT 4.5:1
#   GOOD 5.9:1 | BAD 6.6:1 | WARN 5.0:1
# ACCENT_2 is a graphic/large-area colour, not a text colour on white.
BG = "#F5F7FB"          # page background (light)
CARD = "#FFFFFF"        # card / panel / table surface
CARD_2 = "#EDF2F7"      # secondary surface: inputs, code chips, light fills
NAVY = "#17365D"        # brand identity: sidebar background, major headings
ACCENT = "#2878D0"      # primary blue: actions, active nav, main chart series
ACCENT_2 = "#56A6E8"    # light blue: large-area graphic colour (never body text)
TEXT = "#172B4D"
TEXT_MUTED = "#64748B"
BORDER = "#DCE4EE"
GRID = "#E8EEF7"

GOOD = "#157347"        # semantic positive text/chip colour (AA on white)
BAD = "#B42318"         # semantic negative text/chip colour
WARN = "#B45309"        # semantic warning text/chip colour
NEUTRAL = "#94A3B8"
PIE_TEXT = "#FFFFFF"

# Coordinated chart family (saturated — chart series, accents, indicators only;
# never a card background). Text/status chips keep the darker semantic trio.
TEAL = "#14B8A6"        # sales channels, operations, secondary series
VIOLET = "#8B5CF6"      # customer intelligence, segmentation, model identity
AMBER = "#F59E0B"       # promotions and attention indicators (charts)
ROSE = "#E879A9"        # product analytics and category comparisons
GREEN = "#16A34A"       # positive performance lines/bands (chips use GOOD)
RED = "#EF4444"         # losses and risk lines/bands (chips use BAD)
ORANGE = "#C2410C"      # inventory signal colour: low-cover band (14-30d)

ACCENT_2_SOFT = "rgba(86,166,232,0.16)"
ACCENT_SOFT = "rgba(40,120,208,0.10)"
GOOD_SOFT = "rgba(21,115,71,0.10)"
BAD_SOFT = "rgba(180,35,24,0.08)"
WARN_SOFT = "rgba(180,83,9,0.10)"

# Chart categorical sequence: the first seven follow the platform palette in a
# coordinated rotation; the tail pads dense categorical mixes (up to ~10 slices).
COLORS = [
    ACCENT,
    TEAL,
    VIOLET,
    AMBER,
    ROSE,
    GREEN,
    RED,
    ACCENT_2,
    NAVY,
    NEUTRAL,
]

FONT_STACK = '"Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif'
MONO_STACK = '"Cascadia Code", "SFMono-Regular", Consolas, monospace'

_SHADOW = "0 1px 2px rgba(23,54,93,0.04), 0 10px 28px rgba(23,54,93,0.06)"

CSS = f"""
<style>
:root {{
    --cottonil-bg: {BG};
    --cottonil-card: {CARD};
    --cottonil-card-2: {CARD_2};
    --cottonil-navy: {NAVY};
    --cottonil-accent: {ACCENT};
    --cottonil-accent-2: {ACCENT_2};
    --cottonil-teal: {TEAL};
    --cottonil-violet: {VIOLET};
    --cottonil-amber: {AMBER};
    --cottonil-rose: {ROSE};
    --cottonil-green: {GREEN};
    --cottonil-red: {RED};
    --cottonil-text: {TEXT};
    --cottonil-muted: {TEXT_MUTED};
    --cottonil-border: {BORDER};
    --cottonil-good: {GOOD};
    --cottonil-bad: {BAD};
    --cottonil-warn: {WARN};
}}

html, body, [class*="css"], [data-testid="stAppViewContainer"] {{
    font-family: {FONT_STACK};
}}
.stApp, [data-testid="stAppViewContainer"] {{
    background: {BG};
    color: {TEXT};
}}
[data-testid="stMainBlockContainer"] {{
    max-width: 1500px;
    padding: 1.35rem 2.1rem 3rem 2.1rem;
}}
[data-testid="stHeader"] {{
    background: transparent;
}}
[data-testid="stToolbar"] {{
    right: 1rem;
}}
[data-testid="stAppDeployButton"] {{
    display: none;
}}
#MainMenu, footer {{
    visibility: hidden;
}}
[data-testid="stDecoration"] {{
    display: none;
}}
::selection {{
    background: rgba(40,120,208,0.18);
}}

/* ---------------------------------------------------------------- sidebar -- */
/* Brand navy sidebar: the grouped nav and the pinned brand header both live
   on NAVY; filter widgets the pages add (selects, radios) stay white inputs. */
[data-testid="stSidebar"] {{
    background: {NAVY};
    border-right: 1px solid rgba(9, 20, 38, 0.35);
}}
[data-testid="stSidebar"] > div {{
    background: transparent;
}}
[data-testid="stSidebarContent"] {{
    padding: 0.2rem 0.95rem 2rem 0.95rem;
    /* The empty top strip is owned by stSidebarHeader (logo spacer + collapse
       control). Keep the scroll container static so the pinned brand header
       resolves against stSidebar and stays visible while content scrolls. */
    position: static;
}}
[data-testid="stSidebarHeader"] {{
    height: 64px;
    min-height: 64px;
    margin: 0;
    padding: 0;
    position: relative;    /* keeps the collapse control above the brand row */
    z-index: 3;
}}
[data-testid="stSidebarCollapseButton"] {{
    position: absolute;
    right: 10px;
    top: 18px;
    z-index: 4;
}}
[data-testid="stSidebarNav"] {{
    padding-top: 0.25rem;
}}
[data-testid="stSidebarNavSeparator"] {{
    display: none;         /* the brand header draws the divider */
}}
[data-testid="stSidebarNav"] a {{
    border-radius: 9px;
    color: #CFDDF2;
    margin: 1px 0;
    padding: 4px 8px;
}}
[data-testid="stSidebarNav"] a:hover {{
    background: rgba(255, 255, 255, 0.09);
    color: #FFFFFF;
}}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: rgba(86, 166, 232, 0.26);
    color: #FFFFFF;
    font-weight: 700;
}}
[data-testid="stSidebar"] label {{
    color: #CFDDF2;
    font-size: 0.82rem;
    font-weight: 650;
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
    color: #A8BBD8;
}}
[data-testid="stSidebar"] [role="radiogroup"] label {{
    border-radius: 8px;
    padding: 0.28rem 0.35rem;
}}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {{
    background: rgba(255, 255, 255, 0.10);
}}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked),
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {{
    background: rgba(86, 166, 232, 0.26);
    color: #FFFFFF;
}}

/* Grouped sidebar navigation: compact uppercase section labels and a
   clearly visible active page, using existing tokens only. */
[data-testid="stNavSectionHeader"] {{
    border-radius: 8px;
    color: #8FA6C8;        /* brand-tinted group label on navy */
    font-size: 0.66rem;
    font-weight: 750;
    letter-spacing: 0.11em;
    margin-top: 0.45rem;
    text-transform: uppercase;
}}
[data-testid="stNavSectionHeader"] span {{
    color: inherit;
}}
[data-testid="stSidebarNavLinkContainer"] {{
    margin: 1px 0;
}}
[data-testid="stSidebarNavLink"] {{
    border-radius: 9px;
    color: #CFDDF2;
    font-size: 0.86rem;
    padding: 5px 8px;
}}
[data-testid="stSidebarNavLink"][aria-current="page"] {{
    background: rgba(86, 166, 232, 0.26);
    color: #FFFFFF;
    font-weight: 700;
}}
[data-testid="stSidebarNavLink"] span {{
    font-size: inherit;
}}

/* Brand header, pinned over the empty top strip (§ sidebar shell): Streamlit
   mounts stSidebarNav above all entrypoint sidebar content, so the brand block
   is absolutely positioned against stSidebar with an opaque navy background —
   nav links slide beneath it when the sidebar scrolls. */
[data-testid="stSidebarUserContent"] div.stElementContainer:has(> div .cottonil-brand) {{
    position: static;
}}
[data-testid="stSidebarUserContent"] .cottonil-brand {{
    align-items: center;
    background: {NAVY};
    border-bottom: 1px solid rgba(255, 255, 255, 0.16);
    display: flex;
    gap: 0.65rem;
    left: 20px;
    margin: 0;
    padding: 0.15rem 0.1rem 0.8rem;
    position: absolute;
    right: 20px;
    top: 16px;
    z-index: 1;
}}
.cottonil-brand-mark {{
    align-items: center;
    /* Woven-textile brand mark: crosshatch threads over the brand blue. */
    background:
        repeating-linear-gradient(90deg, rgba(255,255,255,0.22) 0 2px, transparent 2px 7px),
        repeating-linear-gradient(0deg, rgba(10,25,47,0.18) 0 2px, transparent 2px 7px),
        linear-gradient(135deg, {ACCENT_2} 0%, {ACCENT} 65%, #1F63B0 100%);
    border-radius: 10px;
    box-shadow: 0 1px 4px rgba(6, 20, 40, 0.35);
    color: #FFFFFF;
    display: flex;
    font-size: 0.95rem;
    font-weight: 800;
    height: 36px;
    justify-content: center;
    letter-spacing: 0.02em;
    width: 36px;
}}
.cottonil-brand-name {{
    color: #FFFFFF;
    font-size: 0.80rem;
    font-weight: 800;
    letter-spacing: 0.11em;
    line-height: 1.2;
}}
.cottonil-brand-sub {{
    color: #9CB6DB;
    font-size: 0.68rem;
    letter-spacing: 0.02em;
    margin-top: 0.12rem;
}}

/* -------------------------------------------------------------- typography -- */
[data-testid="stMarkdownContainer"] h1 {{
    color: {NAVY};
    font-size: 2rem;
    font-weight: 750;
    letter-spacing: -0.025em;
    line-height: 1.16;
}}
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {{
    color: {NAVY};
    font-weight: 720;
    letter-spacing: -0.015em;
}}
[data-testid="stMarkdownContainer"] h4 {{
    color: {NAVY};
    font-size: 1.08rem;
    font-weight: 720;
    letter-spacing: -0.01em;
    margin-top: 0.35rem;
}}
[data-testid="stMarkdownContainer"] h5 {{
    color: {TEXT};
    font-size: 0.92rem;
    font-weight: 700;
}}
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {{
    color: {TEXT};
}}
[data-testid="stMarkdownContainer"] strong {{
    color: {NAVY};
    font-weight: 700;
}}
[data-testid="stMarkdownContainer"] code {{
    background: {CARD_2};
    border-radius: 5px;
    color: {NAVY};
    font-family: {MONO_STACK};
    font-size: 0.82em;
    padding: 0.10rem 0.30rem;
}}
[data-testid="stCaptionContainer"] p,
.stCaption {{
    color: {TEXT_MUTED};
    font-size: 0.80rem;
    line-height: 1.55;
}}
a {{
    color: {ACCENT};
    text-decoration-color: rgba(40,120,208,0.35);
    text-underline-offset: 2px;
}}
a:hover {{
    color: {NAVY};
}}

/* ------------------------------------------------------------- page header -- */
.cottonil-page-head {{
    border-bottom: 1px solid {BORDER};
    margin-bottom: 1.15rem;
    padding: 0.15rem 0 1.05rem;
}}
.cottonil-eyebrow {{
    color: {ACCENT};
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    margin-bottom: 0.35rem;
    text-transform: uppercase;
}}
.cottonil-page-head h1 {{
    color: {NAVY};
    font-size: 2.02rem;
    font-weight: 760;
    letter-spacing: -0.028em;
    line-height: 1.14;
    margin: 0;
}}
.cottonil-page-sub {{
    color: {TEXT_MUTED};
    font-size: 0.90rem;
    line-height: 1.6;
    margin: 0.55rem 0 0;
    max-width: 1150px;
}}
.cottonil-page-sub strong {{
    color: {TEXT};
    font-weight: 650;
}}
.cottonil-page-sub code {{
    background: {CARD_2};
    border-radius: 5px;
    color: {NAVY};
    font-family: {MONO_STACK};
    font-size: 0.82em;
    padding: 0.08rem 0.28rem;
}}
.cottonil-chip-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.38rem;
    margin-top: 0.62rem;
}}
.cottonil-chip {{
    align-items: center;
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 999px;
    color: {TEXT_MUTED};
    display: inline-flex;
    font-size: 0.69rem;
    font-weight: 650;
    gap: 0.28rem;
    padding: 0.13rem 0.55rem;
}}
.cottonil-chip::before {{
    background: {ACCENT};
    border-radius: 50%;
    content: "";
    height: 5px;
    width: 5px;
}}
.cottonil-chip.tone-good::before {{ background: {GOOD}; }}
.cottonil-chip.tone-warn::before {{ background: {WARN}; }}
.cottonil-chip.tone-bad::before {{ background: {BAD}; }}
.cottonil-chip.tone-neutral::before {{ background: {NEUTRAL}; }}

.cottonil-section {{
    margin: 0.35rem 0 0.75rem;
}}
.cottonil-section h3 {{
    color: {NAVY};
    font-size: 1.14rem;
    font-weight: 720;
    letter-spacing: -0.012em;
    margin: 0;
}}
.cottonil-section p {{
    color: {TEXT_MUTED};
    font-size: 0.80rem;
    line-height: 1.5;
    margin: 0.22rem 0 0;
}}

/* --------------------------------------------------------------- home hero -- */
.cottonil-hero {{
    background: linear-gradient(135deg, {CARD} 0%, #F3F7FD 62%, #EAF2FC 100%);
    border: 1px solid {BORDER};
    border-radius: 20px;
    box-shadow: {_SHADOW};
    margin-bottom: 1.35rem;
    overflow: hidden;
    padding: 2rem 2.15rem 1.85rem;
    position: relative;
}}
.cottonil-hero::after {{
    background: radial-gradient(circle, rgba(40,120,208,0.18), rgba(40,120,208,0));
    border-radius: 50%;
    content: "";
    height: 300px;
    position: absolute;
    right: -90px;
    top: -110px;
    width: 300px;
}}
.cottonil-hero > * {{
    position: relative;
    z-index: 1;
}}
.cottonil-hero h1 {{
    color: {NAVY};
    font-size: 2.45rem;
    font-weight: 780;
    letter-spacing: -0.035em;
    line-height: 1.10;
    margin: 0;
    max-width: 840px;
}}
.cottonil-hero-sub {{
    color: {TEXT_MUTED};
    font-size: 0.96rem;
    line-height: 1.65;
    margin: 0.7rem 0 0;
    max-width: 900px;
}}
.cottonil-hero-meta {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-top: 1.15rem;
}}
.cottonil-hero-meta .cottonil-chip {{
    background: rgba(255,255,255,0.82);
}}

/* ------------------------------------------------------------------- KPI -- */
.cottonil-kpi {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 16px;
    box-shadow: {_SHADOW};
    color: {TEXT};
    height: 100%;
    overflow: hidden;
    padding: 1rem 1.15rem 0.95rem;
    position: relative;
}}
.cottonil-kpi::before {{
    background: linear-gradient(90deg, {ACCENT}, {ACCENT_2});
    content: "";
    height: 3px;
    inset: 0 0 auto 0;
    opacity: 0.9;
    position: absolute;
}}
/* Restrained per-metric accent strips (§5). The strip only adds a small visual
   identity; values, labels and the good/bad delta chips stay authoritative. */
.cottonil-kpi.tone-blue::before {{
    background: linear-gradient(90deg, {ACCENT}, {ACCENT_2});
}}
.cottonil-kpi.tone-teal::before {{
    background: linear-gradient(90deg, {TEAL}, #0D9488);
}}
.cottonil-kpi.tone-violet::before {{
    background: linear-gradient(90deg, {VIOLET}, #7C3AED);
}}
.cottonil-kpi.tone-amber::before {{
    background: linear-gradient(90deg, {AMBER}, #D97706);
}}
.cottonil-kpi.tone-rose::before {{
    background: linear-gradient(90deg, {ROSE}, #DB6D97);
}}
.cottonil-kpi.tone-green::before {{
    background: linear-gradient(90deg, {GREEN}, #15803D);
}}
.cottonil-kpi.tone-red::before {{
    background: linear-gradient(90deg, {RED}, #DC2626);
}}
.cottonil-kpi .cpi-title {{
    color: {TEXT_MUTED};
    font-size: 0.71rem;
    font-weight: 750;
    letter-spacing: 0.09em;
    margin: 0 0 0.38rem;
    text-transform: uppercase;
}}
.cottonil-kpi .cpi-value {{
    color: {NAVY};
    font-size: 1.88rem;
    font-weight: 760;
    letter-spacing: -0.025em;
    line-height: 1.14;
}}
.cottonil-kpi .cpi-delta {{
    border: 1px solid transparent;
    border-radius: 7px;
    display: inline-flex;
    font-size: 0.75rem;
    font-weight: 750;
    gap: 0.25rem;
    line-height: 1.35;
    margin-top: 0.55rem;
    padding: 0.13rem 0.45rem;
}}
.cottonil-kpi .cpi-delta.is-good {{
    background: {GOOD_SOFT};
    border-color: rgba(21,115,71,0.20);
    color: {GOOD};
}}
.cottonil-kpi .cpi-delta.is-bad {{
    background: {BAD_SOFT};
    border-color: rgba(180,35,24,0.20);
    color: {BAD};
}}
.cottonil-kpi .cpi-delta.is-neutral {{
    background: {CARD_2};
    border-color: {BORDER};
    color: {TEXT_MUTED};
}}
.cottonil-kpi .cpi-delta-note {{
    color: {TEXT_MUTED};
    font-size: 0.68rem;
    line-height: 1.4;
    margin-top: 0.25rem;
}}
.cottonil-kpi .cpi-sub {{
    color: {TEXT_MUTED};
    font-size: 0.73rem;
    line-height: 1.48;
    margin-top: 0.5rem;
}}
.cottonil-kpi .cpi-arrow {{
    font-size: 0.68rem;
    line-height: 1.4;
}}

/* ------------------------------------------------------- sidebar footer -- */
.cottonil-sidebar-footer {{
    color: #A8BBD8;
    display: flex;
    align-items: center;
    gap: 0.45rem;
    font-size: 0.72rem;
    line-height: 1.5;
    justify-content: flex-start;
    margin-top: 0.55rem;
}}
.cottonil-sidebar-footer b {{
    color: #CFDDF2;
    font-weight: 650;
}}

/* ------------------------------------------------------------------ charts -- */
[data-testid="stPlotlyChart"] {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 16px;
    box-shadow: 0 1px 2px rgba(23,54,93,0.03);
    padding: 0.6rem 0.65rem 0.25rem;
}}
[data-testid="stDataFrame"],
[data-testid="stDataFrameResizable"] {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
    overflow: hidden;
}}

/* -------------------------------------------------------- controls / states -- */
button[data-testid^="stBaseButton"] {{
    border-radius: 10px;
    font-weight: 650;
    min-height: 2.3rem;
    transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
}}
button[data-testid="stBaseButton-primary"] {{
    background: {ACCENT};
    border-color: {ACCENT};
    color: #FFFFFF;
}}
button[data-testid="stBaseButton-primary"]:hover {{
    background: #1F63B0;
    border-color: #1F63B0;
    color: #FFFFFF;
}}
button[data-testid="stBaseButton-secondary"] {{
    background: {CARD};
    border-color: {BORDER};
    color: {TEXT};
}}
button[data-testid="stBaseButton-secondary"]:hover {{
    background: #F8FBFF;
    border-color: {ACCENT};
    color: {ACCENT};
}}
button:disabled {{
    opacity: 0.55;
}}
[data-baseweb="select"] > div,
[data-baseweb="input"] > div,
[data-baseweb="textarea"] > div {{
    background: {CARD};
    border-color: {BORDER};
    border-radius: 9px;
}}
[data-baseweb="select"] > div:focus-within,
[data-baseweb="input"] > div:focus-within,
[data-baseweb="textarea"] > div:focus-within {{
    border-color: {ACCENT};
    box-shadow: 0 0 0 2px rgba(40,120,208,0.14);
}}
[data-testid="stExpander"] details {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    overflow: hidden;
}}
[data-testid="stExpander"] summary {{
    color: {TEXT};
    font-weight: 650;
}}
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
    border-bottom: 1px solid {BORDER};
    gap: 0.3rem;
}}
[data-testid="stTabs"] [data-baseweb="tab"] {{
    border-radius: 9px 9px 0 0;
    color: {TEXT_MUTED};
    font-weight: 650;
    padding: 0.45rem 0.85rem;
}}
[data-testid="stTabs"] [aria-selected="true"] {{
    background: {ACCENT_SOFT};
    color: {ACCENT};
}}
[data-testid="stAlert"] {{
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) {{
    background: #FFF9EC;
    border-color: #F0D29C;
}}
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) {{
    background: #FEF3F2;
    border-color: #F3B7B0;
}}
[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) {{
    background: #F1F8FF;
    border-color: #BDD9F3;
}}
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) {{
    background: #F0FAF4;
    border-color: #AFDEC3;
}}
[data-testid="stDivider"] hr,
hr {{
    border-color: {BORDER};
    margin: 1.35rem 0;
}}
[data-testid="stCodeBlock"] pre,
pre {{
    background: #F6F8FC;
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

/* -------------------------------------------------------------------- chat -- */
[data-testid="stChatMessage"] {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 16px;
    box-shadow: 0 1px 2px rgba(23,54,93,0.03);
    padding: 0.85rem 1rem;
}}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
    background: #F4F8FE;
    border-color: #CFE1F5;
}}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {{
    color: {TEXT};
    line-height: 1.65;
}}
[data-testid="stChatInput"] {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
    box-shadow: {_SHADOW};
    margin-top: 0.6rem;
}}
[data-testid="stChatInput"] textarea {{
    color: {TEXT};
}}
[data-testid="stChatInput"]:focus-within {{
    border-color: {ACCENT};
    box-shadow: 0 0 0 3px rgba(40,120,208,0.14);
}}

/* --------------------------------------------------------------- a11y / small -- */
a:focus-visible,
button:focus-visible,
[role="button"]:focus-visible,
input:focus-visible,
textarea:focus-visible,
select:focus-visible {{
    outline: 2px solid {ACCENT};
    outline-offset: 2px;
}}
.sr-only {{
    height: 1px;
    margin: -1px;
    overflow: hidden;
    padding: 0;
    position: absolute;
    width: 1px;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
}}
@media (max-width: 900px) {{
    [data-testid="stMainBlockContainer"] {{
        padding: 0.9rem 0.9rem 2rem 0.9rem;
    }}
    .cottonil-page-head h1 {{ font-size: 1.62rem; }}
    .cottonil-page-sub {{ font-size: 0.84rem; }}
    .cottonil-hero {{ padding: 1.35rem 1.2rem; }}
    .cottonil-hero h1 {{ font-size: 1.78rem; }}
    .cottonil-hero-sub {{ font-size: 0.88rem; }}
    .cottonil-kpi .cpi-value {{ font-size: 1.55rem; }}
    [data-testid="stPlotlyChart"] {{ padding: 0.3rem; }}
}}
@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{
        scroll-behavior: auto !important;
        transition-duration: 0.01ms !important;
    }}
}}

/* ------------------------------------------------------------- top bar -- */
.st-key-topbar {{
    background: {NAVY};
    border-radius: 14px;
    padding: 0.45rem 0.9rem;
    margin-bottom: 0.9rem;
    position: sticky;
    top: 0.5rem;
    z-index: 999;
    box-shadow: 0 6px 20px rgba(23,54,93,0.18);
}}
.st-key-topbar .topbar-brand {{ color: #FFFFFF; font-weight: 800; letter-spacing: 0.02em; white-space: nowrap; }}
.st-key-topbar .topbar-crumb {{ color: #CFDDF2; font-size: 0.82rem; white-space: nowrap; }}
.st-key-topbar .topbar-chip {{
    background: rgba(255,255,255,0.13); color: #FFFFFF; border-radius: 999px;
    padding: 0.28rem 0.7rem; font-size: 0.78rem; font-weight: 600; white-space: nowrap;
    display: inline-block; margin-top: 0.35rem;
}}
@media (max-width: 900px) {{
    .st-key-topbar .topbar-crumb {{ display: none; }}
}}

/* ------------------------------------------------------- insight strip -- */
.cottonil-insight {{
    border: 1px solid {BORDER}; border-radius: 14px; padding: 12px 14px; height: 100%;
}}
.cottonil-insight .ins-label {{ font-size: 0.72rem; letter-spacing: 0.07em; text-transform: uppercase; font-weight: 700; color: {TEXT_MUTED}; }}
.cottonil-insight .ins-value {{ font-size: 1.25rem; font-weight: 800; color: {TEXT}; line-height: 1.2; }}
.cottonil-insight .ins-sub {{ font-size: 0.78rem; color: {TEXT_MUTED}; line-height: 1.45; }}
.cottonil-insight.tone-good {{ background: {GOOD_SOFT}; }}
.cottonil-insight.tone-bad {{ background: {BAD_SOFT}; }}
.cottonil-insight.tone-warn {{ background: {WARN_SOFT}; }}
.cottonil-insight.tone-neutral {{ background: {CARD}; }}

</style>
"""

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE = re.compile(r"`([^`]+)`")


def _inline(text: str) -> str:
    """Escape user-visible text, then allow the inline markdown pages already use."""
    safe = html.escape(text, quote=False)
    safe = _BOLD.sub(r"<strong>\1</strong>", safe)
    return _CODE.sub(r"<code>\1</code>", safe)


def apply_theme() -> None:
    """Apply the global stylesheet and the sidebar brand header.

    The brand block is rendered once by the shell (`Home.py` is the runtime
    entrypoint for every registered page, `st.navigation` re-runs it on each
    switch) and styled at the top of the sidebar by the CSS above.
    The version line comes from the installed package metadata
    (`pyproject.toml [project] version`); it is omitted when the metadata is
    unavailable rather than hardcoding a number.
    """
    version = ""
    try:
        from importlib.metadata import version as _pkg_version

        version = f" \u00b7 v{_pkg_version('cottonil')}"
    except Exception:  # noqa: BLE001 - cosmetic line, never fatal
        version = ""
    st.markdown(CSS, unsafe_allow_html=True)
    st.sidebar.markdown(
        '<div class="cottonil-brand">'
        '<div class="cottonil-brand-mark" aria-hidden="true">C</div>'
        "<div>"
        '<div class="cottonil-brand-name">COTTONIL</div>'
        f'<div class="cottonil-brand-sub">Business Assistant{version}</div>'
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------ top bar -----
def topbar(
    *,
    group: str,
    title: str,
    period_label: str,
    data_through: str,
    jump_options: list[tuple[str, str]],
    current_key: str,
) -> str | None:
    """Sticky shell top bar: brand + breadcrumb, quick jump, status chips.

    Rendered by the shell (Home.py) before the page runs. Returns the page
    key chosen in the "Jump to" selectbox when it differs from
    `current_key` (the caller then switches pages), else None. The widget
    key embeds the current page so the selection always reflects where
    the user actually is, even after sidebar navigation.
    """
    titles = [title_ for _, title_ in jump_options]
    keys = [key for key, _ in jump_options]
    current_title = dict(jump_options).get(current_key, title)
    with st.container(key="topbar"):
        c_brand, c_jump, c_period, c_data = st.columns([2.2, 1.5, 1.3, 1.3])
        with c_brand:
            st.markdown(
                '<div class="topbar-brand">COTTONIL <span style="font-weight:500;opacity:.75">Intelligence</span></div>'
                f'<div class="topbar-crumb">{_inline(group)} / {_inline(title)}</div>',
                unsafe_allow_html=True,
            )
        with c_jump:
            chosen = st.selectbox(
                "Jump to",
                titles,
                index=titles.index(current_title) if current_title in titles else 0,
                key=f"topbar_jump_{current_key}",
                label_visibility="collapsed",
            )
        with c_period:
            st.markdown(f'<span class="topbar-chip">{_inline(period_label)}</span>', unsafe_allow_html=True)
        with c_data:
            st.markdown(f'<span class="topbar-chip">Data through {_inline(data_through)} \u00b7 Live</span>', unsafe_allow_html=True)
    chosen_key = keys[titles.index(chosen)] if chosen in titles else current_key
    return chosen_key if chosen_key != current_key else None


# -------------------------------------------------------- insight strip ---
_INSIGHT_TONES = ("good", "bad", "warn", "neutral")


def insight_strip(items: list[dict]) -> None:
    """Up to 3 insight cards: {icon, label, value, sub, tone}.

    Insights are computed by each page from dataframes it already
    queries — this helper only renders. Tones map to the semantic
    *_SOFT backgrounds in the palette.
    """
    items = [item for item in items if item][:3]
    if not items:
        return
    cols = st.columns(len(items))
    for col, item in zip(cols, items, strict=True):
        tone = item.get("tone", "neutral")
        if tone not in _INSIGHT_TONES:
            tone = "neutral"
        icon = item.get("icon", "")
        with col:
            st.markdown(
                f'<div class="cottonil-insight tone-{tone}">'
                f'<div class="ins-label">{_inline(icon + " " if icon else "")}{_inline(str(item.get("label", "")))}</div>'
                f'<div class="ins-value">{_inline(str(item.get("value", "")))}</div>'
                f'<div class="ins-sub">{_inline(str(item.get("sub", "")))}</div>'
                "</div>",
                unsafe_allow_html=True,
            )


# ------------------------------------------------------------- cards ------


@_contextmanager
def chart_card(title: str, subtitle: str | None = None):
    """Titled card wrapper for a chart.

    Charts already receive card chrome from the global CSS
    ([data-testid="stPlotlyChart"]); this wrapper adds the shared
    title/subtitle header above the figure inside a bordered card.
    """
    with st.container(border=True):
        st.markdown(f"**{title}**")
        if subtitle:
            st.caption(subtitle)
        yield


@_contextmanager
def table_card(title: str, subtitle: str | None = None):
    """Titled card wrapper for a dataframe (same chrome as chart_card)."""
    with st.container(border=True):
        st.markdown(f"**{title}**")
        if subtitle:
            st.caption(subtitle)
        yield


def page_header(
    title: str,
    subtitle: str | None = None,
    *,
    eyebrow: str | None = None,
    badges: Sequence[str | tuple[str, str]] = (),
    caption: str | None = None,
    period: str | None = None,
) -> None:
    """Render the shared page header used by every dashboard.

    `caption` is an alias for `subtitle` (§8 of the UI refactor keeps the
    existing signature intact). `period` renders one neutral chip that only
    *displays* the shared reporting window; pages whose metrics are
    period-independent (profile facts, snapshots) must not pass it.
    """
    if subtitle is None:
        subtitle = caption
    eyebrow_html = f'<div class="cottonil-eyebrow">{_inline(eyebrow)}</div>' if eyebrow else ""
    subtitle_html = f'<p class="cottonil-page-sub">{_inline(subtitle)}</p>' if subtitle else ""
    chips: list[str | tuple[str, str]] = []
    if period:
        chips.append((f"Window \u00b7 {period}", "neutral"))
    chips.extend(badges)
    badge_html = ""
    if chips:
        rendered = []
        for badge in chips:
            text, tone = (badge, "") if isinstance(badge, str) else badge
            tone_class = f" tone-{tone}" if tone else ""
            rendered.append(f'<span class="cottonil-chip{tone_class}">{_inline(text)}</span>')
        badge_html = f'<div class="cottonil-chip-row">{"".join(rendered)}</div>'
    st.markdown(
        f'<div class="cottonil-page-head">{eyebrow_html}<h1>{_inline(title)}</h1>'
        f"{subtitle_html}{badge_html}</div>",
        unsafe_allow_html=True,
    )


def hero(
    title: str,
    subtitle: str | None = None,
    *,
    eyebrow: str | None = None,
    meta: Sequence[str | tuple[str, str]] = (),
) -> None:
    """Render the landing-page hero band."""
    eyebrow_html = f'<div class="cottonil-eyebrow">{_inline(eyebrow)}</div>' if eyebrow else ""
    subtitle_html = f'<p class="cottonil-hero-sub">{_inline(subtitle)}</p>' if subtitle else ""
    chips = []
    for item in meta:
        text, tone = (item, "") if isinstance(item, str) else item
        tone_class = f" tone-{tone}" if tone else ""
        chips.append(f'<span class="cottonil-chip{tone_class}">{_inline(text)}</span>')
    meta_html = f'<div class="cottonil-hero-meta">{"".join(chips)}</div>' if chips else ""
    st.markdown(
        f'<div class="cottonil-hero">{eyebrow_html}<h1>{_inline(title)}</h1>'
        f"{subtitle_html}{meta_html}</div>",
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str | None = None, *, eyebrow: str | None = None) -> None:
    """Render a section heading with an optional supporting line."""
    eyebrow_html = f'<div class="cottonil-eyebrow">{_inline(eyebrow)}</div>' if eyebrow else ""
    subtitle_html = f"<p>{_inline(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f'<div class="cottonil-section">{eyebrow_html}<h3>{_inline(title)}</h3>'
        f"{subtitle_html}</div>",
        unsafe_allow_html=True,
    )


def sidebar_footer(*, data_through: str, connected: bool) -> None:
    """Sidebar status line: latest data date + database connectivity (real state)."""
    state = "connected" if connected else "database missing"
    mark_color = GOOD if connected else BAD
    st.sidebar.markdown(
        f'<div class="cottonil-sidebar-footer">'
        f'<b>DuckDB {state}</b>'
        f'<span aria-hidden="true"></span>'
        f'<b>data through {html.escape(data_through)}</b>'
        f'<style>.cottonil-sidebar-footer span{{background:{mark_color};border-radius:50%;'
        f'display:inline-block;height:8px;width:8px;}}</style></div>',
        unsafe_allow_html=True,
    )


KPI_TONES = frozenset({"blue", "teal", "violet", "amber", "rose", "green", "red"})


def kpi_card(
    title: str,
    value: str,
    *,
    delta: str | None = None,
    delta_up: bool = True,
    delta_good: bool = True,
    sub: str | None = None,
    tone: str | None = None,
) -> None:
    """Render a KPI tile with a direction arrow plus a good/bad/neutral status.

    `tone` selects the small top accent strip colour (blue/teal/violet/amber/
    rose/green/red). It is purely a visual family tag for the metric; the
    good/bad delta chip keeps its own semantic colouring. Unknown tones are
    ignored (defaulting to the primary blue gradient).
    """
    tone_class = f" tone-{tone}" if tone in KPI_TONES else ""
    delta_html = ""
    if delta:
        cleaned = delta.strip()
        if cleaned.lower() in {"n/a", "na", "-", "—"}:
            delta_html = '<div class="cpi-delta is-neutral">No comparison available</div>'
        else:
            arrow = "\u25b2" if delta_up else "\u25bc"
            direction = "up" if delta_up else "down"
            tone = "is-good" if delta_good else "is-bad"
            change, comparison = (
                cleaned.split(" vs ", 1) if " vs " in cleaned else (cleaned, "")
            )
            delta_html = (
                f'<div class="cpi-delta {tone}" aria-label="{direction}: {html.escape(cleaned)}">'
                f'<span class="cpi-arrow" aria-hidden="true">{arrow}</span>'
                f"<span>{html.escape(change)}</span></div>"
            )
            if comparison:
                delta_html += (
                    f'<div class="cpi-delta-note">vs {html.escape(comparison)}</div>'
                )
    sub_row = f'<div class="cpi-sub">{html.escape(sub)}</div>' if sub else ""
    st.markdown(
        f'<div class="cottonil-kpi{tone_class}">'
        f'<div class="cpi-title">{html.escape(title)}</div>'
        f'<div class="cpi-value">{html.escape(value)}</div>'
        f"{delta_html}{sub_row}"
        "</div>",
        unsafe_allow_html=True,
    )


def apply_plotly_style(fig) -> None:
    """Uniform light template for every chart in the app."""
    has_title = bool(getattr(fig.layout.title, "text", None))
    labelled_bar = any(
        getattr(trace, "type", None) == "bar"
        and getattr(trace, "orientation", None) == "h"
        and trace.text is not None
        and len(trace.text) > 0
        for trace in fig.data
    )
    short_pie = any(
        getattr(trace, "type", None) == "pie"
        and trace.labels is not None
        and len(list(trace.labels)) <= 8
        for trace in fig.data
    )
    secondary_axis = any(getattr(trace, "yaxis", None) == "y2" for trace in fig.data)
    # Outside labels on horizontal bars and narrow pies need room past the plot
    # edge; a right-hand y-axis also needs room for its ticks and title.
    margin_left = 32 if short_pie else 8
    margin_right = (
        72 if labelled_bar else 96 if secondary_axis else 32 if short_pie else 8
    )
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": TEXT, "family": FONT_STACK, "size": 12},
        title={
            "font": {"color": NAVY, "size": 14},
            "x": 0,
            "xanchor": "left",
        }
        if has_title
        else None,
        margin={
            "l": margin_left,
            "r": margin_right,
            "t": 46 if has_title else 22,
            "b": 30,
        },
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.18,
            "x": 0,
            "font": {"color": TEXT_MUTED, "size": 11},
            "bgcolor": "rgba(0,0,0,0)",
        },
        hovermode="x unified",
        hoverlabel={
            "bgcolor": CARD,
            "bordercolor": BORDER,
            "font": {"color": TEXT, "family": FONT_STACK, "size": 12},
        },
        colorway=COLORS,
        separators=".,",
    )
    fig.update_xaxes(
        automargin=True,
        showgrid=False,
        zeroline=False,
        linecolor=BORDER,
        tickfont={"color": TEXT_MUTED, "size": 11},
        title_font={"color": TEXT_MUTED, "size": 11},
    )
    fig.update_yaxes(
        automargin=True,
        gridcolor=GRID,
        gridwidth=1,
        zeroline=False,
        linecolor=BORDER,
        tickfont={"color": TEXT_MUTED, "size": 11},
        title_font={"color": TEXT_MUTED, "size": 11},
    )
    for trace in fig.data:
        if (
            getattr(trace, "type", None) == "bar"
            and getattr(trace, "orientation", None) == "h"
            and trace.text is not None
        ):
            trace.update(cliponaxis=False)

    # Pies: short mixes get dark labels outside the ring; dense category mixes
    # suppress overlapping labels and let the legend + hover carry the detail.
    for trace in fig.data:
        if getattr(trace, "type", None) != "pie":
            continue
        raw_labels = trace.labels
        labels = list(raw_labels) if raw_labels is not None else []
        if len(labels) > 8:
            trace.update(textinfo="none")
            continue
        trace.update(
            textposition="outside",
            textfont={"color": TEXT, "size": 11},
            outsidetextfont={"color": TEXT, "size": 11},
            automargin=True,
        )


def _compact(value: float) -> tuple[float, str]:
    magnitude = abs(value)
    if magnitude >= 1_000_000_000:  # billion
        return value / 1_000_000_000, "B"
    if magnitude >= 1_000_000:  # million
        return value / 1_000_000, "M"
    if magnitude >= 1_000:  # thousand
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
