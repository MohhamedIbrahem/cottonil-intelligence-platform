"""Perf gate (T112): every registered page renders under the 3-second budget.

Warm pass over all pages populates st.cache_data; the second pass is timed.
Wall-clock includes DuckDB queries + page build, which is the number a user
actually feels. Clock budget is enforced at 3.0 s and can be raised in CI via
COTTONIL_PAGE_BUDGET if hardware demands it.

Pages come from the navigation registry (app/navigation.py) — the 2026-10
refactor removed free-form page discovery, so the perf gate tracks the same 16
registered dashboards plus the shell.
"""

from __future__ import annotations

import os
import pathlib
import sys
import time

import pytest
from streamlit.testing.v1 import AppTest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from app.navigation import page_files

APP_DIR = _ROOT / "app"
PAGES = [APP_DIR / "Home.py", *(APP_DIR / "pages" / name for name in page_files())]
BUDGET = float(os.environ.get("COTTONIL_PAGE_BUDGET", "3.0"))

assert len(PAGES) == 17, f"{len(PAGES)} render targets — shell + 16 dashboards expected"


def _warm() -> None:
    for page in PAGES:
        at = AppTest.from_file(str(page), default_timeout=300)
        at.run()


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_page_under_budget(page):
    _warm()
    at = AppTest.from_file(str(page), default_timeout=300)
    start = time.perf_counter()
    at.run()
    elapsed = time.perf_counter() - start
    assert not at.exception, f"{page.name}: {at.exception[0].value}"
    print(f"  {page.name}: {elapsed:.2f}s (budget {BUDGET:.1f}s)", flush=True)
    assert elapsed < BUDGET, f"{page.name} rendered in {elapsed:.2f}s > {BUDGET:.1f}s"
