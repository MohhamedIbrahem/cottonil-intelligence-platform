"""AI Assistant chat (deck p.23) - US7 chat + US8 shortcut rail (T094/T100/T101).

Every answer is produced by read-only SQL against data/cottonil.duckdb (the
guard allow-lists only curated views + raw dimensions). Each assistant message
can expand its SQL, copy the answer, and jump to the matching dashboard.
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import streamlit as st

from app import data, theme
from assistant import engine, env, goldset, llm
from pipeline import config


@st.cache_data(show_spinner=False)
def data_branches() -> list[str]:
    return data.q(
        "SELECT branch_name_ar FROM views.branch_summary ORDER BY 1"
    ).iloc[:, 0].tolist()

st.set_page_config(
    page_title="AI Assistant · Cottonil",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.apply_theme()

st.title("🤖 Business Assistant")
st.caption(
    "Read-only · grounded in data/cottonil.duckdb · every answer shows its SQL · "
    f"data through {config.DATA_END_DATE} · EGP"
)

VIEW_PAGE_MAP = {
    "sales_enriched": "pages/1_Executive_Overview.py",
    "monthly_sales": "pages/1_Executive_Overview.py",
    "top_products": "pages/2_Sales_Performance.py",
    "product_overview": "pages/2_Sales_Performance.py",
    "campaigns_clean": "pages/2_Sales_Performance.py",
    "returns_enriched": "pages/2_Sales_Performance.py",
    "branch_daily": "pages/3_Branch_Performance.py",
    "branch_summary": "pages/3_Branch_Performance.py",
    "stock_monthly": "pages/4_Inventory_Stock.py",
    "stock_status": "pages/4_Inventory_Stock.py",
    "stock_latest": "pages/4_Inventory_Stock.py",
    "customer_rfm": "pages/5_Customer_Intelligence.py",
    "customer_profile": "pages/5_Customer_Intelligence.py",
}


# ------------------------------------------------------------- state utils --
def _queue_question(question: str) -> None:
    st.session_state.assistant_pending = question
    st.rerun()


def _memory() -> list[dict[str, str]] | None:
    """Last 4 exchanges as engine context (T101 session memory)."""
    turns: list[dict[str, str]] = []
    for m in st.session_state.assistant_msgs[-8:]:
        if m["role"] == "user":
            turns.append({"role": "user", "content": m["content"]})
        elif m.get("sql"):
            turns.append({
                "role": "assistant",
                "content": f"SQL: {m['sql']}\nAnswer: {m.get('narration', '')[:600]}",
            })
    return turns[-8:] or None

if "assistant_msgs" not in st.session_state:
    st.session_state.assistant_msgs = []

with st.sidebar:
    if st.button("🧹 Clear conversation", use_container_width=True):  # T101 reset
        st.session_state.assistant_msgs = []
        st.session_state.assistant_pending = None
        st.rerun()
    st.markdown(
        "**Try:**\n"
        "- What are total net sales all time?\n"
        "- أعلى 5 فروع مبيعاً في 2025\n"
        "- Which customers are at risk of churn?\n"
        "- Show returns by reason\n"
    )
    st.caption(f"Goldset coverage: {len(goldset.GOLDSET)} question/invariant pairs "
               "run in `tests/test_assistant.py`.")
    st.caption("Provider chain: " + " → ".join(llm.describe_providers()))

if not st.session_state.get("assistant_llm_ready"):
    with st.spinner("Connecting to the assistant LLM…"):
        st.session_state.assistant_llm_ready = llm.probe()

if not st.session_state.assistant_llm_ready:
    if env.PROVIDERS:
        rows = "\n".join(
            f"| {provider.name} | {'primary' if index == 0 else 'fallback'} | `{provider.model}` |"
            for index, provider in enumerate(env.PROVIDERS)
        )
        st.warning(
            "The assistant LLM is not reachable. Keys live in `.env` (gitignored) — "
            "verify `GEMINI_API_KEY` / `GROQ_API_KEY` and reload this page.\n\n"
            "| Provider | Role | Model |\n|---|---|---|\n" + rows,
            icon="🔌",
        )
    else:
        st.warning(
            "No assistant LLM provider is configured. Add `GEMINI_API_KEY` + "
            "`GEMINI_MODEL` (primary) and `GROQ_API_KEY` + `GROQ_MODEL` (fallback) "
            "to `.env`, then reload this page.",
            icon="🔌",
        )
    st.stop()

# ------------------------------------------------------- shortcut rail (T100) --
with st.container(border=True):
    st.markdown("#### ⚡ Shortcuts")
    s_cols = st.columns(3)
    with s_cols[0]:
        if st.button("📈 Get insights", use_container_width=True):
            _queue_question(
                "Give me an executive digest of the whole dataset: total net sales, orders, "
                "active customers, average order value, and the best-selling three categories."
            )
    with s_cols[1]:
        if st.button("📝 View report", use_container_width=True):
            _queue_question(
                "Write a short report for the last complete month (September 2026): net sales, "
                "orders, active customers, top-3 branches, and anything notable about returns."
            )
    with s_cols[2]:
        if st.button("📦 Check inventory", use_container_width=True):
            _queue_question(
                "Which locations and categories have the highest stockout risk right now "
                "(latest stock month)? Show the top 10 with their closing units and value."
            )

    t2_cols = st.columns(3)
    with t2_cols[0]:
        branch_choice = st.selectbox(
            "Store performance — branch",
            data_branches(),
            index=None,
            placeholder="pick a branch…",
        )
        if st.button("🏬 Analyze branch", use_container_width=True,
                     disabled=not branch_choice):
            _queue_question(
                f"Show KPIs for branch '{branch_choice}' for calendar 2026: net sales, "
                "orders, average order value, and its rank among all branches by net sales."
            )
    with t2_cols[1]:
        customer_choice = st.text_input(
            "Customer insights — id", placeholder="e.g. C0060015", key="cust_id_input"
        )
        if st.button("👤 Analyze customer", use_container_width=True,
                     disabled=not customer_choice.strip()):
            _queue_question(
                f"Profile customer {customer_choice.strip()}: their RFM tier, total orders, "
                "lifetime value, and their most recent order date."
            )
    with t2_cols[2]:
        if st.button("🚚 Supplier information", use_container_width=True):
            _queue_question(
                "List the top 10 suppliers by number of purchase orders with their total PO "
                "value, average lead time in days, and on-time delivery percentage."
            )

st.divider()

# ---------------------------------------------------------- execution flow --
pending = st.session_state.get("assistant_pending")
if pending:
    st.session_state.assistant_pending = None
    st.session_state.assistant_msgs.append({"role": "user", "content": pending})
    with st.spinner("Reading the dataset… (guarding SQL, executing read-only, narrating)"):
        result = engine.ask(pending, memory=_memory())
    st.session_state.assistant_msgs.append({
        "role": "assistant",
        "narration": result.narration or result.error,
        "sql": result.sql, "df": result.df, "sources": result.sources,
        "truncated": result.truncated, "refusal": result.refusal,
        "attempts": result.attempts, "provider": result.provider,
    })
    if result.df is None and result.sql == "" and not result.refusal:
        st.error(result.error, icon="🔌")

prompt = st.chat_input("Ask in English or Arabic…")
if prompt:
    _queue_question(prompt)

# ---------------------------------------------------------- render history --
for index, message in enumerate(st.session_state.assistant_msgs):
    if message["role"] == "user":
        with st.chat_message("user", avatar="🧍"):
            st.markdown(message["content"])
        continue

    refusal = message.get("refusal", False)
    with st.chat_message("assistant", avatar="🤖"):
        narration = message.get("narration") or ""
        if refusal:
            st.warning(narration, icon="🛑")
        else:
            st.markdown(narration)

        provider = message.get("provider") or ""
        if provider and (env.PRIMARY is None or provider != env.PRIMARY.name):
            st.caption(f"via {provider} (fallback)")

        if message.get("truncated"):
            st.info("Result truncated at 200 rows.", icon="✂️")

        if message.get("df") is not None:
            st.dataframe(message["df"], hide_index=True)

        if message.get("sql"):
            with st.expander("🔍 SQL used for this answer"):
                st.code(message["sql"], language="sql")
                attempts = message.get("attempts") or []
                if attempts:
                    st.caption(" · ".join(attempts))

        if narration and not refusal:
            with st.expander("📋 Copy / export this answer"):
                st.code(narration, language="markdown")  # built-in copy button

        deep_link = next(
            (VIEW_PAGE_MAP[s.split(".")[-1]] for s in message.get("sources", [])
             if s.split(".")[-1] in VIEW_PAGE_MAP),
            None,
        )
        if deep_link:
            st.button("📊 Matched dashboard",
                      key=f"link-{index}-{deep_link}",
                      on_click=st.switch_page, args=(deep_link,))
