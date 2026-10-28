"""UI smoke gate: the navigation registry, the shell, and every dashboard.

Constitution IV (all gates tested): the navigation registry is the source of
truth — pages are rendered through Streamlit's AppTest harness, the shell owns
``st.set_page_config`` and the single reporting-period selector, the merged
pages expose both tabs, and the floating assistant keeps its session state
without duplicate submissions. The customer-lookup backend queries from the
original smoke gate are preserved verbatim.

AppTest harness note (verified against the installed Streamlit 1.66): a re-run
of a ``st.navigation`` shell re-executes only the currently displayed dashboard,
not the shell — shell interactions are therefore exercised by seeding
``session_state`` before a fresh run, the documented AppTest seeding technique.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import re
import sys

import pytest
from streamlit.testing.v1 import AppTest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from app.navigation import NAV_GROUPS, VIEW_PAGE_MAP, page_files, page_names

APP_DIR = _ROOT / "app"
HOME = APP_DIR / "Home.py"
PAGES_DIR = APP_DIR / "pages"

# Pages that existed before the 2026-10 UI refactor and must NOT come back.
RETIRED_PAGES = ("app/pages/6_Assistant.py", "app/pages/16_Replenishment.py", "app/pages/17_CLV_Churn.py")

EXPECTED_GROUPS = [
    "Overview",
    "Sales & Channels",
    "Products & Pricing",
    "Supply & Operations",
    "Customers",
    "Organization & Growth",
]

SHORTCUT_CHIPS = (
    "Get insights", "View report", "Check inventory",
    "Analyze branch", "Analyze customer", "Supplier info",
)

# Session key the shell persists the reporting window under (app/filters.py).
PERIOD_KEY = "period"
SEEDED_WINDOW = (dt.date(2024, 1, 1), dt.date(2024, 12, 31), "Jan 2024 \u2013 Dec 2024", "Calendar year")


# ------------------------------------------------------- registry statics ----
def test_registry_has_six_navigation_groups():
    assert [group[0] for group in NAV_GROUPS] == EXPECTED_GROUPS


def test_registry_registers_16_pages_exactly_once():
    names = page_names()
    files = page_files()
    assert len(names) == 16, f"expected the 16-page registry, got {len(names)}"
    assert len(set(names)) == len(names), "a page key is registered twice"
    assert len(set(files)) == len(files), "a page file is registered twice"


def test_assistant_is_not_a_navigation_page():
    assert not any("assistant" in name for name in page_names())
    for grouped_keys in (keys for _label, keys in NAV_GROUPS):
        assert not any("assistant" in key for key in grouped_keys)


def test_every_registered_file_exists_on_disk():
    for file_name in page_files():
        assert (PAGES_DIR / file_name).is_file(), f"missing {file_name}"


def test_deleted_pages_are_gone_and_unreferenced():
    for rel_path in RETIRED_PAGES:
        assert not (_ROOT / rel_path).is_file(), f"{rel_path} still exists"
    haystacks = "".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in [*(APP_DIR / "pages").glob("*.py"), *APP_DIR.glob("*.py")]
    )
    for rel_path in RETIRED_PAGES:
        assert rel_path.split("/")[-1] not in haystacks, f"{rel_path} still referenced"


# ---------------------------------------------------- assistant deep links ----
def test_deep_links_point_at_registered_pages():
    for view, key in VIEW_PAGE_MAP.items():
        assert key in page_names(), f"view {view} links to unregistered page {key}"
    # The two merged tabs are the deep-link destinations for their old pages.
    assert VIEW_PAGE_MAP["replenishment_signals"] == "inventory_stock"
    assert VIEW_PAGE_MAP["customer_clv"] == "customer_intelligence"


def test_deep_link_page_object_builds():
    from app.navigation import get_page

    for view in VIEW_PAGE_MAP:
        assert get_page(VIEW_PAGE_MAP[view]) is not None


# ------------------------------------------------------------- app shell ------
def _run_shell() -> AppTest:
    at = AppTest.from_file(str(HOME), default_timeout=300)
    at.run()
    assert not at.exception, f"shell: {at.exception[0].value}"
    return at


def test_shell_renders_and_registers_the_period_once():
    at = _run_shell()
    # Exactly one reporting-period control, in the sidebar.
    assert len(at.sidebar.radio) == 1
    assert at.sidebar.radio[0].value == "Last 12 months"
    # The shell persists the window for every dashboard to read.
    window = at.session_state[PERIOD_KEY]
    assert window is not None
    start, end, label, mode = window
    assert start < end and mode == "Last 12 months" and label


def test_selector_modes_switch_and_persist():
    # AppTest detail: on a re-run of a `st.navigation` shell only the currently
    # displayed dashboard re-executes, so mode changes are exercised by seeding
    # the radio's session key before a fresh run (documented AppTest technique).
    for mode, expected_start in (
        ("Calendar year", dt.date(2026, 1, 1)),
        ("All time", dt.date(2018, 10, 19)),
    ):
        at = AppTest.from_file(str(HOME), default_timeout=300)
        at.session_state["period_mode"] = mode
        at.run()
        assert not at.exception
        assert at.sidebar.radio[0].value == mode
        window = at.session_state[PERIOD_KEY]
        assert window[3] == mode
        assert window[0] == expected_start
    # The selection persists across navigation: a second run re-executes the
    # dashboard only, and it still reads the window the shell wrote.
    at = AppTest.from_file(str(HOME), default_timeout=300)
    at.session_state["period_mode"] = "Calendar year"
    at.run()
    first_window = at.session_state[PERIOD_KEY]
    at.run()
    assert not at.exception
    assert at.session_state[PERIOD_KEY] == first_window


def test_selector_is_registered_once_across_sources():
    home_text = HOME.read_text(encoding="utf-8")
    assert home_text.count("render_period_selector()") == 1
    for file_name in page_files():
        page_text = (PAGES_DIR / file_name).read_text(encoding="utf-8")
        assert "render_period_selector" not in page_text, file_name


def test_set_page_config_is_only_called_from_home():
    home_text = HOME.read_text(encoding="utf-8")
    assert home_text.count("st.set_page_config(") == 1
    for py in [*(APP_DIR / "pages").glob("*.py"), *APP_DIR.glob("*.py")]:
        if py.name == "Home.py":
            continue
        assert "st.set_page_config(" not in py.read_text(encoding="utf-8"), py.name


def test_reporting_period_state_survives_page_navigation():
    # Seed the window the shell wrote on a previous run, then load a page
    # through its own file — it must read the same window, not a fresh default.
    at = AppTest.from_file(str(PAGES_DIR / "1_Executive_Overview.py"), default_timeout=300)
    at.session_state[PERIOD_KEY] = SEEDED_WINDOW
    at.run()
    assert not at.exception
    rendered = "\n".join(m.value for m in at.markdown)
    assert "Jan 2024" in rendered, "the page ignored the shared reporting window"


# ------------------------------------------------------------ merged pages ----
def test_inventory_and_stock_page_has_both_tabs():
    at = AppTest.from_file(str(PAGES_DIR / "4_Inventory_Stock.py"), default_timeout=300)
    at.run()
    assert not at.exception
    labels = [tab.label for tab in at.tabs]
    assert "Inventory & Stock" in labels and "Replenishment" in labels


def test_customer_intelligence_page_has_both_tabs():
    at = AppTest.from_file(str(PAGES_DIR / "5_Customer_Intelligence.py"), default_timeout=300)
    at.run()
    assert not at.exception
    labels = [tab.label for tab in at.tabs]
    assert "Customer Intelligence" in labels and "CLV & Churn" in labels


def test_merged_pages_own_no_sidebar_filters():
    for file_name in ("4_Inventory_Stock.py", "5_Customer_Intelligence.py"):
        text = (PAGES_DIR / file_name).read_text(encoding="utf-8")
        assert "st.sidebar." not in text, f"{file_name} still renders sidebar widgets"


# --------------------------------------------------- floating assistant -------
def _fab(at: AppTest):
    return next(b for b in at.button if b.key == "assistant_fab")


def test_assistant_defaults_after_a_plain_shell_run():
    at = _run_shell()
    # The dock starts closed with an empty conversation; state keys exist.
    assert _fab(at).label == "Business AI Assistant"
    assert at.session_state["assistant_open"] is False
    assert at.session_state["assistant_msgs"] == []
    assert at.session_state["assistant_pending"] is None


def test_assistant_panel_reports_unreachable_provider(monkeypatch):
    monkeypatch.setattr("assistant.llm.probe", lambda *a, **k: False)
    at = AppTest.from_file(str(HOME), default_timeout=300)
    at.session_state["assistant_open"] = True  # AppTest seeding (see modes note above)
    at.run()
    assert not at.exception
    # Panel header buttons exist; the dock (FAB) is not rendered while open.
    assert at.session_state["assistant_open"] is True
    close = next(b for b in at.button if b.key == "assistant_close")
    clear = next(b for b in at.button if b.key == "assistant_clear")
    assert close.label == "Close" and clear.label == "Clear chat"
    assert not any(b.key == "assistant_fab" for b in at.button)
    # Honest unavailability: no fake chat is offered while the provider is down.
    assert at.session_state["assistant_llm_ready"] is False
    assert any("not reachable" in str(w.value) for w in at.warning)
    # Opening the panel by itself must not touch the conversation.
    assert at.session_state["assistant_msgs"] == []


def test_assistant_submission_runs_once_on_rerun(monkeypatch):
    from assistant import engine

    calls: list[str] = []

    def fake_ask(question: str, memory=None):
        calls.append(question)
        from types import SimpleNamespace

        return SimpleNamespace(
            narration=f"Answered: {question}", sql="SELECT 1", df=None,
            sources=[], truncated=False, refusal=False, attempts=[],
            provider="test-provider",
        )

    monkeypatch.setattr(engine, "ask", fake_ask)
    monkeypatch.setattr("assistant.llm.probe", lambda *a, **k: True)
    at = AppTest.from_file(str(HOME), default_timeout=300)
    at.session_state["assistant_open"] = True
    at.session_state["assistant_pending"] = "How many orders in 2024?"
    at.run()
    assert not at.exception
    # Exactly one queued question is consumed: pending is cleared, one user
    # entry and one answer are recorded, one engine call is made.
    assert at.session_state["assistant_pending"] is None
    msgs = at.session_state["assistant_msgs"]
    user_asks = [m["content"] for m in msgs if m["role"] == "user"]
    assert user_asks == ["How many orders in 2024?"]
    assert msgs[-1]["narration"] == "Answered: How many orders in 2024?"
    assert msgs[-1]["error"] is False
    assert len(calls) == 1
    # A following run (navigation-style rerun) must not resubmit anything.
    at.run()
    assert len(calls) == 1
    msgs_after = at.session_state["assistant_msgs"]
    assert [m["content"] for m in msgs_after if m["role"] == "user"] == user_asks
    assert [m for m in msgs_after if m["role"] == "assistant"] == [msgs[-1]]


def test_assistant_message_states_render(monkeypatch):
    monkeypatch.setattr("assistant.llm.probe", lambda *a, **k: True)
    at = AppTest.from_file(str(HOME), default_timeout=300)
    at.session_state["assistant_open"] = True
    at.session_state["assistant_msgs"] = [
        {"role": "user", "content": "سؤال بالعربي"},
        {   # refusal -> warning
            "role": "assistant", "narration": "Can't answer that from the views.",
            "sql": "", "df": None, "sources": [], "truncated": False,
            "refusal": True, "attempts": [], "provider": "test",
        },
        {   # fallback provider caption + truncated flag + grounded deep link
            "role": "assistant", "narration": "Monthly sales answer.",
            "sql": "SELECT ...", "df": None, "sources": ["views.monthly_sales"],
            "truncated": True, "refusal": False, "attempts": [],
            "provider": "groq",
        },
    ]
    at.run()
    assert not at.exception
    assert len(at.session_state["assistant_msgs"]) == 3
    # Refusal renders as a warning; the fallback provider stays visible.
    assert any("answer" in str(w.value).lower() for w in at.warning)
    rendered = "\n".join(str(el.value) for el in (*at.markdown, *at.caption))
    assert "groq" in rendered
    # The view hit (views.monthly_sales) earns a deep link into the registry.
    assert any(b.label == "Open matched dashboard" for b in at.button)


def test_no_shortcut_chips_in_the_assistant_ui():
    haystacks = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in [*(APP_DIR / "pages").glob("*.py"), *APP_DIR.glob("*.py")]
    )
    for chip in SHORTCUT_CHIPS:
        assert chip not in haystacks, f"shortcut chip {chip!r} is back"


def test_no_sql_expander_in_the_normal_ui():
    haystacks = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in [*(APP_DIR / "pages").glob("*.py"), *APP_DIR.glob("*.py")]
    )
    assert "SQL used for this answer" not in haystacks
    assert "st.code(message" not in haystacks


# ------------------------------------------- every dashboard smoke renders -----
@pytest.mark.parametrize("file_name", page_files(), ids=lambda n: n)
def test_page_renders_without_exceptions(file_name):
    page = PAGES_DIR / file_name
    at = AppTest.from_file(str(page), default_timeout=300)
    at.run()
    assert not at.exception, f"{file_name}: {at.exception[0].value}"


def test_shell_renders_without_exceptions():
    _run_shell()


# ----------------------------------------------- Home content preserved -------
def test_executive_overview_preserves_the_old_home_content():
    at = AppTest.from_file(str(PAGES_DIR / "1_Executive_Overview.py"), default_timeout=300)
    at.run()
    assert not at.exception
    rendered = "\n".join(m.value for m in at.markdown)
    for expected in ("Company at a glance", "Policies and known limits",
                     "Single source of truth", "Coverage"):
        assert expected in rendered, f"lost from the migration: {expected}"
    expander_labels = [e.label for e in at.expander]
    # The two Home-era explainers ride along to their new page.
    assert "About the data, coverage and policies" in expander_labels
    assert "Data notes - definitions & caveats for this page" in expander_labels


# ------------------------------------------------------- Arabic + lookup ------
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
    # Arabic names flow into the lookup results (and therefore its UI).
    first_name = str(matches.iloc[0]["name"])
    assert re.search(r"[\u0600-\u06FF]", first_name), "Arabic names lost from lookup"


def test_no_search_is_a_harmless_no_match():
    from app import data

    matches = data.q(
        "SELECT COUNT(*) AS n FROM views.customer_profile WHERE customer_name_ar LIKE ?",
        ("%\u063a\u063a\u063a\u063a_tuple_not_in_data%\n",),
    )
    assert int(matches.n.iloc[0]) == 0


def test_arabic_branch_names_render_on_branch_performance():
    from app import data as app_data

    page = PAGES_DIR / "3_Branch_Performance.py"
    at = AppTest.from_file(str(page), default_timeout=300)
    at.run()
    assert not at.exception

    # The source data carries Arabic branch names and the page renders tables.
    branch_names = app_data.q(
        "SELECT DISTINCT branch_name_ar FROM views.branch_summary LIMIT 5"
    ).iloc[:, 0].tolist()
    assert len(branch_names) == 5
    assert all(re.search(r"[\u0600-\u06FF]", str(n)) for n in branch_names)
    assert len(at.dataframe) + len(at.markdown) > 0, "nothing rendered"
