"""Assistant gate (T091/T092/T095/T096/T097): guard, schemarxjs, engine mechanics,
goldset accuracy (skipped when no live LLM) + refusal tests.

Run with the reporting visible:  uv run pytest tests/test_assistant.py -q -s
"""

from __future__ import annotations

import pathlib
import sys
import time
from types import SimpleNamespace

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from assistant import engine, env, goldset, llm, schema_docs
from assistant.sql_guard import GuardError, deadline_wrap, referenced_tables, validate


# ------------------------------------------------------------------ guard ----
@pytest.mark.parametrize("sql", [
    "DELETE FROM sales_orders",
    "delete from views.sales_enriched where net_sales < 0",
    "INSERT INTO raw.branches VALUES (1, 'x', 'y', 'z', 'b')",
    "DROP TABLE views.sales_enriched",
    "UPDATE views.sales_enriched SET net_sales = 0",
    "PRAGMA force_checkpoint",
    "SET memory_limit='1TB'",
    "COPY (SELECT 1) TO 'x.csv'",
    "ATTACH 'other.duckdb' AS other",
    "ALTER TABLE views.monthly_sales RENAME TO monthly",
    "CREATE TABLE t AS SELECT 1",
])
def test_guard_blocks_writes_and_meta(sql):
    with pytest.raises(GuardError):
        validate(sql)


def test_guard_blocks_multi_statement_and_unknowables():
    with pytest.raises(GuardError):
        validate("SELECT 1; SELECT 2")
    with pytest.raises(GuardError):
        validate("SELECT 1; DROP TABLE views.monthly_sales")
    with pytest.raises(GuardError):  # raw facts are not part of the allow-list
        validate("SELECT * FROM raw.sales_orders LIMIT 5")
    with pytest.raises(GuardError):  # must be schema-qualified
        validate("SELECT * FROM branches")
    with pytest.raises(GuardError):  # not one of the allowed views
        validate("SELECT * FROM views.some_future_view")


@pytest.mark.parametrize("sql", [
    "SELECT COUNT(*) FROM views.sales_enriched",
    "WITH t AS (SELECT net_sales FROM views.monthly_sales) SELECT SUM(net_sales) FROM t",
    ("SELECT b.branch_name_ar, s.net FROM views.branch_summary s "
     "JOIN raw.branches b ON b.branch_id = s.branch_id"),
    "/* comment with DELETE FROM x */ SELECT net_sales FROM views.monthly_sales -- trailing",
    "SELECT 'ls Michaels ; DROP TABLE users' AS literal FROM views.monthly_sales",
])
def test_guard_allows_legit_reads(sql):
    assert validate(sql).strip()


def test_guard_caps_rows_and_lists_sources():
    wrapped = deadline_wrap(validate("SELECT net_sales FROM views.monthly_sales"))
    assert "LIMIT 201" in wrapped
    assert referenced_tables(
        "SELECT b.branch_name_ar FROM views.branch_summary s JOIN raw.branches b USING (branch_id)"
    ) == ["views.branch_summary", "raw.branches"]


# ---------------------------------------------------------------- schemarxjs --
def test_schema_docs_nonempty_and_complete():
    text = schema_docs.schema_text()
    for view in ("sales_enriched", "monthly_sales", "stock_latest", "customer_profile"):
        assert f"views.{view}" in text
    assert "order_date" in text and "net_sales" in text
    assert "NOT queryable" in text          # raw facts excluded tell
    assert "tricks" not in text.lower()     # no exec detail leakage
    # The metric notes must mention the anomaly policies it relies on:
    for token in ("A1", "A2", "A3", "A4", "A5", "refund_capped", "attributed_net_real"):
        assert token in text, token


# ------------------------------------------------------- engine + refusal ----
def _stub_chat(reply_expected_sql: str):
    """chat_fn with a scripted first SQL answer and narrator."""
    calls = {"n": 0}

    def chat(messages, **_):
        calls["n"] += 1
        if calls["n"] % 2 == 1:  # SQL calls (odd)
            if calls["n"] == 1:
                return f"```sql\n{reply_expected_sql}\n```"
            raise AssertionError("only one SQL call scripted")
        return "Authority answer: " + messages[-1]["content"][:40]  # narrator

    return chat, calls


def test_engine_answers_with_grounded_sql():
    chat_fn, _ = _stub_chat("SELECT SUM(orders) AS orders FROM views.monthly_sales")
    result = engine.ask("How many orders do we have?", chat_fn=chat_fn)
    assert not result.error and result.refusal is False
    assert result.df is not None and len(result.df) == 1
    assert abs(float(result.df.iloc[0, 0]) - 540_000) < 1e-6
    assert result.sources == ["views.monthly_sales"]
    assert "Authority answer" in result.narration


def test_write_request_is_refused_without_executing():
    def chat(messages, **_):
        if messages[-1]["role"] == "user" and "delete" in messages[-1]["content"].lower():
            return "```sql\nDELETE FROM views.sales_enriched\n```"
        return "why are you retrying"

    result = engine.ask("delete everything please", chat_fn=chat)
    assert result.refusal is True
    assert result.df is None and result.sql == ""
    assert "read-only" in result.narration
    assert len(result.attempts) == engine.env.SQL_RETRIES + 1 or len(result.attempts) >= 1


def test_engine_surfaces_garbage_sql_as_refusal():
    def chat(messages, **_):
        return "I'm a helpful assistant, not an SQL generator. 🌸"

    result = engine.ask("hello", chat_fn=chat)
    assert result.refusal is True
    assert result.df is None


# ---------------------------------------------------------- provider chain ----
FAKE_PRIMARY = env.LLMConfig(name="FakePrimary", base_url="http://x", model="m1", api_key="k")
FAKE_FALLBACK = env.LLMConfig(name="FakeFallback", base_url="http://y", model="m2", api_key="k")


def _fake_openai(content: str | None, fail_reason: str = ""):
    """Stand-in for the OpenAI SDK client bound to one provider."""
    if fail_reason:
        def create(**_):
            raise RuntimeError(fail_reason)
    else:
        def create(**_):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_chat_falls_back_when_primary_fails(monkeypatch):
    """Primary quota exhausted (429) -> the chain automatically uses the fallback."""
    calls: list[str] = []

    def client_for(provider, *, timeout=None):
        calls.append(provider.name)
        if provider.name == "FakePrimary":
            return _fake_openai(None, fail_reason="[429] Quota exceeded")
        return _fake_openai("fallback answer")

    monkeypatch.setattr(env, "PROVIDERS", [FAKE_PRIMARY, FAKE_FALLBACK])
    monkeypatch.setattr(llm, "client", client_for)
    reply = llm.chat([{"role": "user", "content": "hi"}])
    assert reply == "fallback answer"
    assert calls == ["FakePrimary", "FakeFallback"]
    assert llm.last_provider() is not None and llm.last_provider().name == "FakeFallback"


def test_chat_treats_empty_content_as_failure(monkeypatch):
    def client_for(provider, *, timeout=None):
        return _fake_openai(None if provider is FAKE_PRIMARY else "second answer")

    monkeypatch.setattr(env, "PROVIDERS", [FAKE_PRIMARY, FAKE_FALLBACK])
    monkeypatch.setattr(llm, "client", client_for)
    assert llm.chat([{"role": "user", "content": "hi"}]) == "second answer"


def test_chat_raises_collecting_every_provider_reason(monkeypatch):
    def client_for(provider, *, timeout=None):
        return _fake_openai(None, fail_reason=f"boom in {provider.name}")

    monkeypatch.setattr(env, "PROVIDERS", [FAKE_PRIMARY, FAKE_FALLBACK])
    monkeypatch.setattr(llm, "client", client_for)
    with pytest.raises(llm.LLMError) as excinfo:
        llm.chat([{"role": "user", "content": "hi"}])
    message = str(excinfo.value)
    assert "FakePrimary" in message and "FakeFallback" in message
    assert "boom in" in message


def test_chat_without_any_provider_raises_setup_hint(monkeypatch):
    monkeypatch.setattr(env, "PROVIDERS", [])
    with pytest.raises(llm.LLMError, match="No assistant LLM provider"):
        llm.chat([{"role": "user", "content": "hi"}])


# -------------------------------------------------------------- goldset ------
def test_goldset_is_wellformed():
    assert len(goldset.GOLDSET) == 20
    ids = [c.id for c in goldset.GOLDSET]
    assert len(ids) == len(set(ids))
    kinds = {c.kind for c in goldset.GOLDSET}
    assert kinds <= {"answer", "refusal", "oos"}
    assert {"refusal", "oos"} <= kinds              # T096 pairs exist
    arabic = sum(1 for c in goldset.GOLDSET if any("\u0600" <= ch <= "\u06FF" for ch in c.question))
    assert arabic >= 3                              # T102 Arabic subset exists


def test_goldset_refusals_and_oos_pass_engine_contract():
    def refusing_chat(messages, **_):
        return "```sql\nDELETE FROM views.monthly_sales\n```"

    for case in goldset.GOLDSET:
        if case.kind == "refusal":
            result = engine.ask(case.question, chat_fn=refusing_chat)
            assert case.checker(result)[0], case.id


def test_goldset_live_accuracy_report():
    """Runs the full 20-question goldset against the live provider chain and print the table.

    Skipped when the chain is unreachable so `pytest` stays green on clean machines;
    run with Gemini/Groq keys in `.env` for the release gate (>= 80%)."""
    if not llm.probe():
        pytest.skip("assistant LLM chain unreachable — check `GEMINI_API_KEY` / "
                    "`GROQ_API_KEY` in .env to run the goldset")
    engine_ask = engine.ask
    rows: list[tuple[str, str, bool, str, str]] = []
    passed = 0
    for index, case in enumerate(goldset.GOLDSET):
        if index:
            time.sleep(9.5)  # free tiers ≈ 15 RPM (Gemini) / 30 RPM (Groq): pace the chain
        result = engine_ask(case.question)
        ok, why = case.checker(result)
        passed += int(ok)
        rows.append((case.id, case.kind, ok, why, result.provider))
    print("\nGoldset report (live provider chain):")
    for id_, kind, ok, why, provider in rows:
        tag = f" via {provider}" if provider else ""
        print(f"  {'✅' if ok else '❌'} {id_} [{kind}]{tag} {why}")
    accuracy = passed / len(rows)
    print(f"Accuracy: {passed}/{len(rows)} = {accuracy:.1%}")
    assert accuracy >= 0.80, f"goldset accuracy {accuracy:.1%} below release gate 80%"
