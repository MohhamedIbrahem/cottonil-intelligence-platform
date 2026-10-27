"""Floating Business Assistant widget (§7) — replaces the standalone page.

`render_assistant_bubble()` is called once from the application shell
(`app/Home.py`) before the page runs, so the assistant is available on every
registered dashboard without each page mounting its own copy.

Feasibility gate (§7.1) — verified with the installed Streamlit version and CSS
only: fixed bottom-right positioning via the keyed-container CSS class
(`.st-key-<key>`, documented `key`-as-CSS-class behaviour of layout
containers), open/close state in `st.session_state`, text entry + send via a
native `st.form` (Enter submits; the Send button submits; the supported
alternative to `st.chat_input` inside a floated container, §7.6), and history
persistence across reruns because messages live in `assistant_msgs`. No custom
components, no injected JavaScript (`st.html` drops JS), no undocumented APIs.

Preserved session keys (§7.5): `assistant_msgs`, `assistant_pending`,
`assistant_llm_ready`; plus `_memory()` and the exact `engine.ask()` record
shape of the old chat page. Provider/fallback status, refusal warnings,
truncated-response info, copy-to-markdown, and grounded-view deep links stay.

Deliberately absent from the normal UI (§7.7): the SQL expander, raw SQL text,
attempts narration, and the six shortcut chips — engine internals are
untouched, presentation only.

Submission idempotency (2026-10-27 fix): `clear_on_submit` is a FRONTEND
behaviour — Streamlit does not clear the server-side value of a form's text
field, so `st.text_input(...)` returns the last submitted text on EVERY
rerun. Gating the request queue on that value (the first implementation) made
each rerun re-queue the same question and call `engine.ask()` again —
dozens of duplicate answers with no further interaction (measured: 153 calls
from one submission before the fix). The submission is therefore captured
ONLY in the Send button's `on_click` callback (`_queue_submit`), which runs
before the script body; the script body only renders and consumes. Every
request carries an increasing `request_id`, is marked processing before the
engine call, and is finalized in `finally`: one submission -> at most one
logical request, and provider failures produce a single error bubble.
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[1]))

import streamlit as st

from app import theme
from app.navigation import VIEW_PAGE_MAP, get_page
from assistant import engine, env, llm

_OPEN_KEY = "assistant_open"          # panel open state
_MSGS_KEY = "assistant_msgs"          # preserved session key (§7.5)
_PENDING_KEY = "assistant_pending"    # preserved session key (§7.5)
_READY_KEY = "assistant_llm_ready"    # preserved session key (§7.5)

_INPUT_KEY = "assistant_input"        # composer text field (inside the form)
_SEQ_KEY = "assistant_seq"            # monotonically increasing request ids
_LAST_REQUEST_KEY = "assistant_last_request"   # id of the request now queued
_PROCESSING_KEY = "assistant_processing"       # True while engine.ask() runs

_MEMORY_WINDOW = 8                    # last 8 entries -> ~4 exchanges of context

# Rendered once per run. Every color resolves to an existing app.theme token
# (shadows are rgba() of the NAVY token 0x17365D = rgb(23,54,93); user bubbles
# reuse ACCENT_SOFT). Anchors are the container keys declared below.
_STYLE = f"""
<style>
/* ---- thinking indicator keyframes ---- */
@keyframes assistant-pulse {{
    0%, 80%, 100% {{ opacity: 0.3; transform: scale(0.8); }}
    40% {{ opacity: 1; transform: scale(1.0); }}
}}
.assistant-thinking {{
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 0.6rem 0.8rem;
}}
.assistant-thinking span {{
    background: {theme.ACCENT};
    border-radius: 50%;
    display: inline-block;
    height: 8px;
    width: 8px;
    animation: assistant-pulse 1.4s ease-in-out infinite;
}}
.assistant-thinking span:nth-child(2) {{ animation-delay: 0.16s; }}
.assistant-thinking span:nth-child(3) {{ animation-delay: 0.32s; }}
.assistant-thinking-label {{
    color: {theme.TEXT_MUTED};
    font-size: 0.76rem;
    margin-left: 6px;
}}
/* ---- floating action button (closed dock) ---- */
.st-key-assistant-dock {{
    background: transparent;
    border: none;
    bottom: 24px;
    box-shadow: none;
    margin: 0;
    min-height: 0;
    padding: 0;
    position: fixed;
    right: 24px;
    width: 60px;
    z-index: 1001;
}}
/* Button styling — targets Streamlit's button inside the dock container.
   The data-testid selector is version-sensitive; the container-key selector
   (.st-key-assistant-dock) is the stable anchor. */
.st-key-assistant-dock button[data-testid="stBaseButton-secondary"],
.st-key-assistant-dock button {{
    background: {theme.ACCENT};
    border-color: {theme.ACCENT};
    border-radius: 50%;
    color: {theme.PIE_TEXT};
    height: 60px;
    padding: 0;
    transition: box-shadow 120ms ease, filter 120ms ease;
    width: 60px;
}}
.st-key-assistant-dock button:hover {{
    box-shadow: 0 6px 18px rgba(23,54,93,0.22);
    filter: brightness(0.92);
}}
.st-key-assistant-dock button p {{
    display: none; /* icon-only circle; the real label stays for screen readers */
}}
.st-key-assistant-dock button svg {{
    height: 22px;
    width: 22px;
}}
/* ---- open panel ---- */
.st-key-assistant-panel {{
    background: {theme.CARD};
    border: 1px solid {theme.BORDER};
    border-radius: 20px;
    bottom: 96px;
    box-shadow: 0 18px 48px rgba(23,54,93,0.16);
    max-height: min(600px, calc(100dvh - 130px));
    overflow-y: auto;
    padding: 0.85rem 0.95rem 0.8rem;
    position: fixed;
    right: 24px;
    width: min(400px, calc(100vw - 32px));
    z-index: 1001;
}}
.st-key-assistant-panel .assistant-panel-title {{
    color: {theme.NAVY};
    font-size: 0.92rem;
    font-weight: 700;
    line-height: 1.25;
}}
.st-key-assistant-panel .assistant-panel-sub {{
    color: {theme.TEXT_MUTED};
    font-size: 0.68rem;
    line-height: 1.4;
    margin-top: 0.1rem;
}}
/* Header buttons — fallback without data-testid for resilience */
.st-key-assistant-panel button {{
    border-radius: 8px;
    min-height: 0;
    padding: 0.1rem 0.3rem;
}}
.st-key-assistant-panel button p {{
    display: none; /* icon-only header buttons; `help` carries the meaning */
}}
.st-key-assistant-panel button svg {{
    height: 16px;
    width: 16px;
}}
.st-key-assistant-panel [data-testid="stChatMessage"] {{
    border: 1px solid {theme.BORDER};
    border-radius: 12px;
    box-shadow: none;
    padding: 0.55rem 0.7rem;
}}
.st-key-assistant-panel [data-testid="stChatMessage"]:has(
    [data-testid="stChatMessageAvatarUser"]
) {{
    background: {theme.ACCENT_SOFT};
}}
.st-key-assistant-panel [data-testid="stMarkdownContainer"] p {{
    color: {theme.TEXT};
    font-size: 0.82rem;
    line-height: 1.5;
}}
.st-key-assistant-panel caption, .st-key-assistant-panel [data-testid="stCaptionContainer"] {{
    font-size: 0.72rem;
}}
.st-key-assistant-panel [data-baseweb="input"] > div {{
    background: {theme.CARD};
    border-color: {theme.BORDER};
}}
/* Truncation notice */
.assistant-truncated {{
    background: {theme.ACCENT_SOFT};
    border-radius: 6px;
    color: {theme.TEXT_MUTED};
    font-size: 0.72rem;
    margin-top: 0.3rem;
    padding: 0.25rem 0.5rem;
}}
@media (max-width: 640px) {{
    .st-key-assistant-panel {{
        bottom: 84px;
        height: calc(100dvh - 114px);
        max-height: none;
        right: 12px;
        width: calc(100vw - 24px);
    }}
    .st-key-assistant-dock {{
        bottom: 18px;
        right: 18px;
    }}
}}
</style>
"""


def _ensure_state() -> None:
    """Single clear place for widget state initialization."""
    for key, default in (
        (_OPEN_KEY, False),
        (_MSGS_KEY, []),
        (_PENDING_KEY, None),
        (_SEQ_KEY, 0),
        (_LAST_REQUEST_KEY, 0),
        (_PROCESSING_KEY, False),
    ):
        if key not in st.session_state:
            st.session_state[key] = default


def _memory() -> list[dict[str, str]] | None:
    """Last 4 exchanges as engine context (T101 session memory; unchanged)."""
    turns: list[dict[str, str]] = []
    for message in st.session_state[_MSGS_KEY][-_MEMORY_WINDOW:]:
        if message["role"] == "user":
            turns.append({"role": "user", "content": message["content"]})
        elif message.get("sql"):
            turns.append({
                "role": "assistant",
                "content": f"SQL: {message['sql']}\nAnswer: {message.get('narration', '')[:600]}",
            })
    return turns or None


def _clear_chat() -> None:
    st.session_state[_MSGS_KEY] = []
    st.session_state[_PENDING_KEY] = None


def _open() -> None:
    st.session_state[_OPEN_KEY] = True


def _close() -> None:
    st.session_state[_OPEN_KEY] = False


def _probe_llm() -> bool:
    """One reachability probe per session; the panel reports the honest state."""
    if not st.session_state.get(_READY_KEY):
        with st.spinner("Connecting to the assistant LLM…"):
            st.session_state[_READY_KEY] = llm.probe()
    return bool(st.session_state[_READY_KEY])


def _process_pending() -> None:
    """Consume exactly one queued question per run; finalize state in finally.

    `_PENDING_KEY` is written ONLY by `_queue_submit()` (one write per real
    submission event), so reruns and history renders can never start a new
    request here. Failure of the engine call becomes ONE error bubble — a
    provider outage or 429 storm can never multiply into duplicate messages.
    """
    state = st.session_state
    question = state.get(_PENDING_KEY)
    if not question or state.get(_PROCESSING_KEY):
        return
    state[_PENDING_KEY] = None          # consumed BEFORE any engine work
    state[_PROCESSING_KEY] = True       # marked BEFORE engine.ask(...) (§fix 4)
    state[_MSGS_KEY].append({
        "role": "user", "content": question,
        "request_id": state.get(_LAST_REQUEST_KEY),
    })
    try:
        with st.chat_message("assistant"):
            st.html(
                '<div class="assistant-thinking">'
                '<span></span><span></span><span></span>'
                '<span class="assistant-thinking-label">Analysing…</span>'
                '</div>'
            )
            result = engine.ask(question, memory=_memory())
        state[_MSGS_KEY].append({
            "role": "assistant",
            "request_id": state.get(_LAST_REQUEST_KEY),
            "narration": result.narration or result.error,
            "sql": result.sql,               # kept for memory context, never rendered
            "df": result.df, "sources": result.sources,
            "truncated": result.truncated, "refusal": result.refusal,
            "attempts": result.attempts, "provider": result.provider,
            # engine-level failure (transport etc.): flag it for st.error display
            "error": bool(result.df is None and result.sql == "" and not result.refusal),
        })
    except Exception as exc:  # noqa: BLE001 - one honest failure bubble, never a retry loop
        # Streamlit's own control-flow exceptions (RerunException, StopException)
        # derive from BaseException, so they pass through untouched.
        state[_MSGS_KEY].append({
            "role": "assistant",
            "request_id": state.get(_LAST_REQUEST_KEY),
            "narration": f"The assistant request failed: {exc}",
            "sql": "", "df": None, "sources": [],
            "truncated": False, "refusal": False, "attempts": [],
            "provider": "", "error": True,
        })
    finally:
        state[_PROCESSING_KEY] = False   # finalized: the request is done either way


def _queue_submit() -> None:
    """`on_click` of the Send button: the ONLY writer of `assistant_pending`.

    Runs BEFORE the script body on the actual submission event (button click
    or Enter in the field), so one event queues exactly one request. The
    composer's text field is cleared here too: `clear_on_submit` is applied
    by the browser only, and a leftover server-side value is exactly what
    made reruns re-queue the same question before this fix. Replays of a
    submit event are idempotent: an empty field or an already-in-flight
    identical pending is never queued twice.
    """
    state = st.session_state
    text = (state.get(_INPUT_KEY) or "").strip()
    state[_INPUT_KEY] = ""              # the composer is event-driven now
    if not text or state.get(_PROCESSING_KEY):
        return
    if state.get(_PENDING_KEY) == text:  # identical replay, nothing to queue
        return
    state[_SEQ_KEY] = state.get(_SEQ_KEY, 0) + 1
    state[_LAST_REQUEST_KEY] = state[_SEQ_KEY]
    state[_PENDING_KEY] = text


def _render_history() -> None:
    messages = st.session_state[_MSGS_KEY]
    if not messages:
        st.caption(
            "Ask in English or Arabic. Every answer comes from read-only SQL "
            "over the curated views — grounded in the dataset, no browsing."
        )
    for index, message in enumerate(messages):
        if message["role"] == "user":
            with st.chat_message("user"):
                st.markdown(message["content"])
            continue

        with st.chat_message("assistant"):
            narration = message.get("narration") or ""
            if message.get("refusal", False):
                st.warning(narration)
            elif message.get("error", False):
                st.error(narration)
            elif not narration:
                # Prose generation failed but the query succeeded: show the
                # rows once; nothing here ever re-runs SQL to get new prose.
                st.warning(
                    "The answer text could not be generated, but the query "
                    "ran successfully — see the result table below."
                )
            else:
                st.markdown(narration)

            provider = message.get("provider") or ""
            if provider and (env.PRIMARY is None or provider != env.PRIMARY.name):
                st.caption(f"via {provider} (fallback)")

            # Hide the raw table inside the compact panel; the same numbers are
            # in the narration. Kept accessible via the copy expander below.
            if message.get("df") is not None:
                with st.expander("Result table"):
                    st.dataframe(message["df"], hide_index=True)

            if narration and not message.get("refusal", False):
                with st.expander("Copy / export this answer"):
                    st.code(narration, language="markdown")  # built-in copy button

            if message.get("truncated", False):
                st.html(
                    '<div class="assistant-truncated">'
                    '⚠ Results were limited to 200 rows. '
                    'Refine your question for a narrower dataset.'
                    '</div>'
                )

            deep_key = next(
                (VIEW_PAGE_MAP[s.split(".")[-1]] for s in message.get("sources", [])
                 if s.split(".")[-1] in VIEW_PAGE_MAP),
                None,
            )
            if deep_key:
                st.button(
                    "Open matched dashboard",
                    key=f"assistant-link-{index}",
                    on_click=st.switch_page,
                    args=(get_page(deep_key),),
                )


def _render_composer() -> None:
    """Form input row (§7.6 supported alternative to chat_input in a panel).

    Enter in the text field submits the form; clicking Send submits too.
    NOTHING here reads the widget's returned value: a submitted value
    persists server-side across reruns (clear_on_submit is frontend-only),
    so gating queueing on the return value re-queued the same question on
    every rerun — the replicate-forever bug. `_queue_submit`, the Send
    button's on_click callback, is the only queueing path.
    """
    with st.form("assistant_form", clear_on_submit=True, border=False):
        cols = st.columns([1, 0.24])
        with cols[0]:
            st.text_input(
                "Ask in English or Arabic…",
                key=_INPUT_KEY,
                placeholder="Ask in English or Arabic…",
                label_visibility="collapsed",
            )
        with cols[1]:
            st.form_submit_button(
                "Send", icon=":material/send:", type="primary", width="stretch",
                on_click=_queue_submit,
            )


def _render_panel() -> None:
    """Open panel: header + status, scrollable history, composer (§7.3)."""
    ready = _probe_llm()
    columns = st.columns([1, 0.14, 0.14])
    with columns[0]:
        st.markdown(
            "<div class='assistant-panel-title'>Business Assistant</div>"
            "<div class='assistant-panel-sub'>"
            + (" · ".join(llm.describe_providers()) if ready else "provider not reachable")
            + "</div>",
            unsafe_allow_html=True,
        )
    with columns[1]:
        st.button(
            "Clear chat", icon=":material/clear_all:", key="assistant_clear",
            on_click=_clear_chat, help="Clear the conversation",
            width="content",
        )
    with columns[2]:
        st.button(
            "Close", icon=":material/close:", key="assistant_close",
            on_click=_close, help="Close the assistant panel",
            width="content",
        )
    if not ready:
        if env.PROVIDERS:
            st.warning(
                "The assistant LLM is not reachable. Keys live in `.env` "
                "(gitignored) — verify `GEMINI_API_KEY` / `GROQ_API_KEY`, then "
                "reopen the panel."
            )
        else:
            st.warning(
                "No assistant LLM provider is configured. Add `GEMINI_API_KEY` + "
                "`GEMINI_MODEL` (primary) and `GROQ_API_KEY` + `GROQ_MODEL` "
                "(fallback) to `.env`."
            )
    st.container(height=6, border=False)
    with st.container(key="assistant_history", height=420, border=False):
        _render_history()
    st.container(height=6, border=False)
    if ready:
        _render_composer()


def _render_fab() -> None:
    """Circular fixed button; opens the panel (§7.2)."""
    st.button(
        "Business Assistant",
        icon=":material/forum:",
        key="assistant_fab",
        on_click=_open,
        help="Open the business assistant chat",
        width=60,
    )


def render_assistant_bubble() -> None:
    """Draw the dock once; the shell calls it before the current page runs."""
    _ensure_state()
    st.html(_STYLE)
    # Queue processing happens regardless of panel state so a pending
    # question (e.g. queued, then navigation rerun) is never lost.
    _process_pending()
    if st.session_state[_OPEN_KEY]:
        with st.container(border=False, key="assistant-panel"):
            _render_panel()
    else:
        with st.container(border=False, key="assistant-dock"):
            _render_fab()
