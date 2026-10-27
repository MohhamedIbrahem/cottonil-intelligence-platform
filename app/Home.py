"""Application shell and single entrypoint (app/Home.py).

Dashboard pages live in ``app/pages/`` and are registered in
``app/navigation.py`` (six groups, 16 dashboards). This file is the frame
around them, in render order:

1. ``st.set_page_config`` + the design system — the ONLY page-config call.
2. The shared reporting-period selector — the ONLY renderer (``app/filters.py``).
3. A sidebar footer with the real latest-data date and database state.
4. The floating Business Assistant widget (available on every dashboard).
5. Grouped navigation via ``st.navigation`` and ``page.run()``.

No dashboard-specific calculations live here: the Executive Overview page owns
the company-level KPI strip that used to sit on this file.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Bootstrap: allow `from app import ...` when launched as app/Home.py.
_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[1]))

import streamlit as st

from app import theme
from app.assistant_widget import render_assistant_bubble
from app.filters import render_period_selector
from app.navigation import build_navigation
from pipeline import config

st.set_page_config(
    page_title="Cottonil Intelligence · Business Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.apply_theme()

if not config.DB_PATH.exists():
    st.error(
        "The DuckDB database has not been built yet. Build it first, then reload."
    )
    st.code("uv run build", language="bash")
    st.stop()

# The shared reporting-period selector — rendered exactly once, in the shell.
render_period_selector()

# Real status line: latest data date + database connectivity.
theme.sidebar_footer(data_through=config.DATA_END_DATE, connected=config.DB_PATH.exists())

# Floating Business Assistant — one dock shared by every dashboard.
render_assistant_bubble()

# Grouped enterprise navigation; expanded keeps every group visible.
# BUILD_NOTE: Streamlit mounts the grouped nav above other sidebar content; a
# brand block below the nav is not supported natively, so the brand identity
# rides on the app header + page titles (documented limitation, §4.3).
page = st.navigation(build_navigation(), expanded=True)
page.run()
