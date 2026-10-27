"""Assistant engine: question -> guarded SQL -> read-only execution -> narrative.

Flow (T094 contract, retry policy T092, guard T091, prompts T093):
1. ask the LLM for one fenced ```sql block (<= 1 + SQL_RETRIES attempts);
   validation or execution failures are fed back to the model for a retry.
2. execute the validated statement read-only with a wall-clock cap
   (assistant.env.SQL_TIMEOUT) enforced through a worker thread + con.interrupt().
3. narrate the result with a second LLM call that sees question + SQL + rows.

`chat_fn` is injectable for tests; the default is assistant.llm.chat.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field

import duckdb
import pandas as pd

from assistant import env, llm
from assistant.prompts import narrate_system_prompt, sql_system_prompt
from assistant.sql_guard import GuardError, deadline_wrap, referenced_tables, validate
from pipeline import config

_FENCE = re.compile(r"```(?:sql|SQL)?\s*\n?(.*?)\n?```", re.DOTALL)

_REFUSAL_TEXT = (
    "I can't run that request — the assistant is read-only and only answers questions "
    "about the Cottonil dataset with SELECT queries.\n"
    "لا أستطيع تنفيذ هذا الطلب — المساعد للقراءة فقط ويجيب عن أسئلة بيانات كوتونيل فقط."
)


@dataclass
class AskResult:
    question: str
    sql: str = ""
    df: pd.DataFrame | None = None
    narration: str = ""
    sources: list[str] = field(default_factory=list)
    attempts: list[str] = field(default_factory=list)   # per-attempt guard/SQL errors
    refusal: bool = False
    error: str = ""                                     # non-empty on hard failure
    truncated: bool = False
    provider: str = ""                                  # LLM that produced the SQL ("" = injected fn)


def extract_sql(reply: str) -> str:
    """First ```sql fence if present, else a bare-looking statement."""
    match = _FENCE.search(reply or "")
    text = match.group(1) if match else (reply or "")
    if not match:
        pos = min(
            (p for p in (reply.find("SELECT"), reply.find("WITH")) if p >= 0),
            default=-1,
        )
        text = reply[pos:] if pos >= 0 else ""
    return text.strip()


def _execute(sql: str) -> pd.DataFrame:
    """Read-only execution with a wall-clock cap via worker thread + interrupt."""
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    holder: dict[str, object] = {}

    def work() -> None:
        try:
            holder["df"] = con.execute(deadline_wrap(sql)).df()
        except Exception as exc:  # noqa: BLE001 - re-raised in caller thread
            holder["error"] = exc

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(env.SQL_TIMEOUT)
    if worker.is_alive():
        con.interrupt()
        worker.join(5.0)
        try:
            con.close()
        except Exception:  # noqa: BLE001, S110 - best-effort cleanup after timeout
            pass
        raise TimeoutError(
            f"Query exceeded the {env.SQL_TIMEOUT:.0f}s read-only cap and was cancelled."
        )
    try:
        error = holder.get("error")
        if error is not None:
            raise error  # type: ignore[misc]
        return holder["df"]  # type: ignore[return-value]
    finally:
        try:
            con.close()
        except Exception:  # noqa: BLE001, S110 - best-effort; connection may already be closed
            pass


def _table_markdown(df: pd.DataFrame, rows: int) -> str:
    """Dependency-free markdown rendering of at most `rows` rows."""
    small = df.head(rows)

    def fmt(value: object) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        if isinstance(value, float):
            text = f"{value:,.2f}".rstrip("0").rstrip(".")
            return text or "0"
        return str(value)

    header = [str(c) for c in small.columns]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    lines += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in small.itertuples(index=False)]
    return "\n".join(lines)


def ask(question: str, *, chat_fn=llm.chat, memory: list[dict[str, str]] | None = None) -> AskResult:
    """Full pipeline for one user question.

    `memory` is an optional list of prior turns ({"role", "content"} pairs) from
    the UI session (T101); it is inserted as context AFTER the system prompt so
    follow-up questions ("and for 2025?") resolve reasonably.
    """
    result = AskResult(question=question)
    history: list[dict[str, str]] = [{"role": "system", "content": sql_system_prompt()}]
    history.extend(memory or [])
    history.append({"role": "user", "content": question})

    for attempt in range(env.SQL_RETRIES + 1):
        try:
            reply = chat_fn(history)
        except llm.LLMError as exc:
            result.error = str(exc)
            return result
        if chat_fn is llm.chat and llm.last_provider() is not None:
            result.provider = llm.last_provider().name

        candidate = extract_sql(reply)
        if not candidate and re.search(r"REFUSAL\s*:", reply or "", re.IGNORECASE):
            # The model legally declined (prompt refusal contract): honor it as a
            # refusal immediately instead of burning attempts on empty SQL.
            result.attempts.append("model refusal: " + " ".join(reply.split())[:120])
            result.refusal = True
            result.narration = _REFUSAL_TEXT
            return result
        try:
            sql = validate(candidate)
        except GuardError as exc:
            result.attempts.append(f"attempt {attempt + 1} guard: {exc}")
            history += [
                {"role": "assistant", "content": reply},
                {"role": "user", "content": (
                    f"Your SQL was rejected: {exc}\n"
                    "Send a corrected single ```sql block that obeys the contract, or reply "
                    "with 'REFUSAL: <short reason>' if the request is not answerable."
                )},
            ]
            continue

        try:
            df = _execute(sql)
        except TimeoutError as exc:
            result.error = str(exc)
            return result
        except duckdb.Error as exc:
            result.attempts.append(f"attempt {attempt + 1} sql: {exc}")
            history += [
                {"role": "assistant", "content": reply},
                {"role": "user", "content": (
                    "DuckDB rejected your SQL with this error:\n"
                    f"{exc}\nSend exactly one corrected ```sql block."
                )},
            ]
            continue

        result.sql = sql
        result.sources = referenced_tables(sql)
        result.df = df
        result.truncated = len(df) > env.MAX_ROWS
        _narrate(result, chat_fn=chat_fn)
        return result

    # Write-shaped requests never survive the guard: friendly refusal (T094/T097).
    result.refusal = True
    result.error = "; ".join(result.attempts[-1:]) or "Request not answerable."
    result.narration = _REFUSAL_TEXT
    return result


def _narrate(result: AskResult, *, chat_fn) -> None:
    payload = (
        f"Question: {result.question}\n\n"
        f"Executed SQL:\n{result.sql}\n\n"
        f"Result (head):\n{_table_markdown(result.df, env.NARRATE_ROWS)}"
        if result.df is not None else ""
    )
    try:
        result.narration = chat_fn([
            {"role": "system", "content": narrate_system_prompt()},
            {"role": "user", "content": payload},
        ])
    except llm.LLMError:
        result.narration = (
            "The answer text service is unavailable, but the query ran successfully - "
            f"see the result table ({len(result.df):,} rows) and SQL below."
        )
