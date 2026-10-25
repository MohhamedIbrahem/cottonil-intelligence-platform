"""Perf gate (T112): every page renders under the 3-second budget.

A warm pass over all pages populates st.cache_data; the second pass is timed.
Wall-clock includes DuckDB queries + page build, which is the number a user
actually feels. Clock budget is enforced at 3.0 s and can be raised in CI via
COTTONIL_PAGE_BUDGET if hardware demands it.
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

APP_DIR = _ROOT / "app"
PAGES = [APP_DIR / "Home.py", *sorted((APP_DIR / "pages").glob("*.py"))]
BUDGET = float(os.environ.get("COTTONIL_PAGE_BUDGET", "3.0"))


def _llm_reachable() -> bool:
    from assistant import llm

    return llm.probe()


def _warm() -> None:
    for page in PAGES:
        at = AppTest.from_file(str(page), default_timeout=300)
        at.run()


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_page_under_budget(page):
    _warm()
    at = AppTest.from_file(str(page), default_timeout=300)
    if page.name == "6_Assistant.py" and not _llm_reachable():
        pytest.skip("assistant LLM down - the fail-fast banner is not the perf claim")
    start = time.perf_counter()
    at.run()
    elapsed = time.perf_counter() - start
    assert not at.exception, f"{page.name}: {at.exception[0].value}"
    print(f"  {page.name}: {elapsed:.2f}s (budget {BUDGET:.1f}s)", flush=True)
    assert elapsed < BUDGET, f"{page.name} rendered in {elapsed:.2f}s > {BUDGET:.1f}s"
