"""Regression tests for the duplicate-answer incident (2026-10-27).

Faithful harness: ``AppTest.from_function`` executes ONLY the widget on every
``.run()`` — the navigation shell re-runs just the mounted page, which would
hide the widget across runs. ``engine.ask`` is replaced by a counting fake
whose record shape matches the real ``AskResult`` (narration/sql/df/sources/
truncated/refusal/attempts/provider/error); ``llm.probe`` is pinned to True so
nothing reaches the network.

Root cause of the incident, measured before the fix: `clear_on_submit` is a
frontend-only behaviour, so the server-side value of the composer's
``st.text_input`` persisted; `_render_composer` gated queueing on that value
plus `st.rerun()` — 8 simulated reruns produced 153 ``engine.ask`` calls and
153 duplicate question bubbles from ONE submission.
"""

from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

import pandas as pd
from streamlit.testing.v1 import AppTest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_INPUT_KEY = "assistant_input"          # composer text field key


def widget_script() -> None:  # executed once per AppTest run
    from app.assistant_widget import render_assistant_bubble

    render_assistant_bubble()


def _send_click(at: AppTest):
    """The form's submit button element (AppTest exposes it in at.button)."""
    return next(b for b in at.button if b.key == "FormSubmitter:assistant_form-Send")


def _harness(monkeypatch, ask) -> tuple[AppTest, list[str]]:
    """A widget-only AppTest with the given engine.ask and an online probe."""
    import assistant.engine as engine_mod
    import assistant.llm as llm_mod

    calls: list[str] = []

    def counting_ask(question: str, memory=None) -> SimpleNamespace:
        result = ask(question, memory=memory)
        calls.append(question)
        return result

    monkeypatch.setattr(engine_mod, "ask", counting_ask)
    monkeypatch.setattr(llm_mod, "probe", lambda *a, **k: True)
    at = AppTest.from_function(widget_script, default_timeout=60)
    at.session_state["assistant_open"] = True
    at.run()          # first run renders the open panel + composer
    assert not at.exception
    return at, calls


def _answer(question: str, memory=None) -> SimpleNamespace:
    return SimpleNamespace(
        narration=f"Answered: {question}", sql="SELECT 1",
        df=None, sources=[], truncated=False, refusal=False,
        attempts=[], provider="gemini", error="",
    )


# == existing history / stale state: render only ==================================
def test_existing_state_and_history_never_trigger_requests(monkeypatch):
    """THE reported incident: stale composer value + open panel + reruns."""
    at, calls = _harness(monkeypatch, _answer)
    at.session_state[_INPUT_KEY] = "top 10 branches"  # server-side leftover
    at.session_state["assistant_msgs"] = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "narration": "Hi! ask me about the data.", "sql": "",
         "df": None, "sources": [], "truncated": False, "refusal": False,
         "attempts": [], "provider": "gemini"},
    ]
    for _ in range(5):
        at.run()
        assert not at.exception
    assert calls == [], "a rerun must never start a new provider request"
    assert at.session_state["assistant_pending"] is None
    assert at.session_state["assistant_processing"] is False
    assert len(at.session_state["assistant_msgs"]) == 2  # untouched


# == one submission -> one request, no matter how many reruns follow ==============
def test_single_submission_asks_exactly_once_across_reruns(monkeypatch):
    at, calls = _harness(monkeypatch, _answer)
    at.session_state[_INPUT_KEY] = "top 10 branches"
    _send_click(at).set_value(True)  # ONE real submission event
    at.run()
    assert not at.exception
    for _ in range(5):
        at.run()
    assert calls == ["top 10 branches"], f"engine.ask called {len(calls)}x"
    msgs = at.session_state["assistant_msgs"]
    assert [m["content"] for m in msgs if m["role"] == "user"] == ["top 10 branches"]
    assert [m for m in msgs if m["role"] == "assistant"] == [msgs[-1]]
    user_record, answer_record = msgs
    assert user_record["request_id"] == answer_record["request_id"] == 1
    assert at.session_state["assistant_pending"] is None
    assert at.session_state["assistant_processing"] is False
    # The composer was cleared when the submission was queued (idempotency root).
    assert at.session_state[_INPUT_KEY] == ""


def test_replayed_submit_of_the_same_event_is_idempotent(monkeypatch):
    at, calls = _harness(monkeypatch, _answer)
    at.session_state[_INPUT_KEY] = "top 10 branches"
    _send_click(at).set_value(True)
    at.run()
    # A second Send click of the (now cleared) field must queue nothing.
    _send_click(at).set_value(True)
    at.run()
    at.run()
    assert calls == ["top 10 branches"], f"replayed submit fired {len(calls)}x"
    assert len(at.session_state["assistant_msgs"]) == 2


def test_a_new_real_question_gets_a_new_request_id(monkeypatch):
    """Idempotency guards replays, not legitimate follow-up questions."""
    at, calls = _harness(monkeypatch, _answer)
    at.session_state[_INPUT_KEY] = "top 10 branches"
    _send_click(at).set_value(True)
    at.run()
    # Submitting again with the widget's set_value emulates typing: after the
    # first submission a committed server-side value exists, which the AppTest
    # wire serializes over plain session_state writes.
    at.text_input(key=_INPUT_KEY).set_value("branch count for 2025")
    _send_click(at).set_value(True)
    at.run()
    assert calls == ["top 10 branches", "branch count for 2025"]
    msgs = at.session_state["assistant_msgs"]
    ids = [m["request_id"] for m in msgs if m["role"] == "user"]
    assert ids == [1, 2], f"request ids must be stable and unique: {ids}"


# == provider outage: bounded to ONE ask, ONE error bubble ========================
def test_provider_429_storm_is_one_request_one_error_message(monkeypatch):
    calls: list[str] = []

    def storming_ask(question: str, memory=None) -> SimpleNamespace:
        calls.append(question)
        raise RuntimeError(
            "All assistant LLM providers failed — Gemini: [429] rate limit "
            "exceeded; Groq: [429] Too Many Requests."
        )

    at, _ = _harness(monkeypatch, storming_ask)
    at.session_state[_INPUT_KEY] = "top 10 branches"
    _send_click(at).set_value(True)
    at.run()
    assert not at.exception
    for _ in range(5):
        at.run()
        # finalized in finally: no request stays "processing" across runs
        assert at.session_state["assistant_processing"] is False
    assert calls == ["top 10 branches"], f"outage re-triggered {len(calls)} requests"
    msgs = at.session_state["assistant_msgs"]
    errors = [m for m in msgs if m["role"] == "assistant" and m.get("error")]
    assert len(errors) == 1, "the 429 storm must surface as ONE error bubble"
    assert "429" in errors[0]["narration"]
    assert len(msgs) == 2


# == SQL succeeded but prose failed: show the result once, never re-run ===========
def test_sql_result_is_shown_once_when_prose_fails(monkeypatch):
    import app.assistant_widget as widget_mod

    # `from_function` runs the script from a temp file, so `st.Page` inside
    # `get_page()` cannot resolve the real pages/ directory; the deep-link
    # button arg is irrelevant to what this test proves. Stub it.
    monkeypatch.setattr(widget_mod, "get_page", lambda key: object())

    calls: list[str] = []

    def prose_failing_ask(question: str, memory=None) -> SimpleNamespace:
        calls.append(question)
        return SimpleNamespace(
            narration="", sql="SELECT branch, net FROM views.branch_summary LIMIT 10",
            df=pd.DataFrame({"branch": ["Egypt"], "net": [1.0]}),
            sources=["views.branch_summary"], truncated=False, refusal=False,
            attempts=[], provider="groq", error="",
        )

    at, _ = _harness(monkeypatch, prose_failing_ask)
    at.session_state[_INPUT_KEY] = "top 10 branches"
    _send_click(at).set_value(True)
    at.run()
    assert not at.exception
    for _ in range(3):
        at.run()
    assert calls == ["top 10 branches"], "SQL must never be re-run for prose"
    assert len(at.session_state["assistant_msgs"]) == 2
    rendered = "\n".join(str(el.value) for el in (*at.markdown, *at.warning))
    assert "query ran successfully" in rendered
    assert any(e.label == "Result table" for e in at.expander)


# == pending across rerun bursts (requirement 8) ==================================
def test_pending_request_survives_reruns_and_asks_once(monkeypatch):
    at, calls = _harness(monkeypatch, _answer)
    at.session_state["assistant_pending"] = "How many orders in 2024?"
    at.run()
    assert not at.exception
    for _ in range(3):
        at.run()
        assert at.session_state["assistant_processing"] is False
    assert calls == ["How many orders in 2024?"]
    assert at.session_state["assistant_pending"] is None
    msgs = at.session_state["assistant_msgs"]
    assert [m["content"] for m in msgs if m["role"] == "user"] == ["How many orders in 2024?"]
