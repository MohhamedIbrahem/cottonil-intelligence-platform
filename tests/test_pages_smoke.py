"""UI smoke gate: every page of the app renders without exceptions.

Constitution IV (all gates tested): boots app/Home.py and every app/pages/*.py
through Streamlit's AppTest harness in all sidebar period modes, and asserts
zero exceptions. Also exercises the customer-lookup backend queries directly.
"""

from __future__ import annotations

import pathlib
import sys

import pytest
from streamlit.testing.v1 import AppTest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

APP_DIR = _ROOT / "app"
MODES = ("Last 12 months", "Calendar year", "All time")

PAGE_FILES = [APP_DIR / "Home.py", *sorted((APP_DIR / "pages").glob("*.py"))]
assert len(PAGE_FILES) >= 2, "no pages discovered under app/pages/"


@pytest.mark.parametrize("page", PAGE_FILES, ids=lambda p: p.name)
def test_page_renders_without_exceptions(page):
    at = AppTest.from_file(str(page), default_timeout=300)
    at.run()
    assert not at.exception, f"{page.name}: {at.exception[0].value}"
    # Exercise the period selector on every page that renders it.
    radios = at.sidebar.radio
    if radios:
        at.sidebar.radio[0].set_value("Calendar year")
        at.run()
        assert not at.exception, f"{page.name} (calendar): {at.exception[0].value}"
        at.sidebar.radio[0].set_value("All time")
        at.run()
        assert not at.exception, f"{page.name} (all time): {at.exception[0].value}"


def test_customer_lookup_backend_returns_rows():
    from app import data

    matches = data.q(
        """
        SELECT customer_id, customer_name_ar AS name, rfm_tier AS tier,
               orders_lifetime AS orders, lifetime_value
        FROM views.customer_profile
        WHERE customer_name_ar LIKE ? OR CAST(customer_id AS VARCHAR) LIKE ?
        ORDER BY lifetime_value DESC LIMIT 8
        """,
        ("%1%", "%1%"),
    )
    assert not matches.empty
    first_id = str(matches.iloc[0].customer_id)

    history = data.q(
        """
        SELECT CAST(order_date AS DATE) AS date, sales_order_id AS order_id,
               SUM(net_sales) AS net_egp, COUNT(*) AS lines
        FROM views.sales_enriched
        WHERE customer_id = ?
        GROUP BY order_date, sales_order_id
        ORDER BY order_date DESC LIMIT 20
        """,
        (first_id,),
    )
    assert not history.empty
    assert (history.net_egp > 0).all()


def test_no_search_is_a_harmless_no_match():
    from app import data

    matches = data.q(
        "SELECT COUNT(*) AS n FROM views.customer_profile WHERE customer_name_ar LIKE ?",
        ("%\u063a\u063a\u063a\u063a_tuple_not_in_data%\n",),
    )
    assert int(matches.n.iloc[0]) == 0
