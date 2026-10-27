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
from app.navigation import build_navigation, group_for_key, key_for_title, page_names
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
_period = render_period_selector()

# Real status line: latest data date + database connectivity.
theme.sidebar_footer(data_through=config.DATA_END_DATE, connected=config.DB_PATH.exists())

# Grouped enterprise navigation (App Shell v3): only the group containing
# the active page stays expanded, so the 16-page sidebar stays scannable.
# BUILD_NOTE: Streamlit mounts the grouped nav above other sidebar content;
# the brand identity therefore rides on the sidebar brand header rendered
# by theme.apply_theme() plus the top bar below.
_nav_dict = build_navigation()
# The st.Page objects inside the navigation dict, in registry order —
# jump targets must be these exact objects, not re-created copies.
_nav_pages = {
    key: page_obj
    for key, page_obj in zip(
        page_names(),
        [page_obj for group_pages in _nav_dict.values() for page_obj in group_pages],
        strict=True,
    )
}
page = st.navigation(_nav_dict, expanded=False)
_current_key = key_for_title(page.title or "")
_current_group = group_for_key(_current_key)

# Sticky top bar: brand + breadcrumb, quick jump, period/data chips.
_jump = theme.topbar(
    group=_current_group,
    title=page.title or "",
    period_label=_period[2],
    data_through=config.DATA_END_DATE,
    jump_options=[(key, _nav_pages[key].title or key) for key in page_names()],
    current_key=_current_key,
)
if _jump:
    st.switch_page(_nav_pages[_jump])

# Floating Business Assistant — one dock shared by every dashboard,
# aware of the page the user is on (contextual suggestions + badge).
render_assistant_bubble(_current_key)

page.run()
