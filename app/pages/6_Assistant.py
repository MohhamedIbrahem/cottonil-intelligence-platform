"""AI Assistant chat (deck p.23) - ask questions, get grounded answers (US7, T094).

Every answer is produced by read-only SQL against data/cottonil.duckdb (the
guard allow-lists only curated views + raw dimensions); each assistant message
can expand its SQL and jump to the matching dashboard (deep links).
"""

from __future__ import annotations

import sys
from pathlib import Path

_FILE = Path(__file__).resolve()
sys.path.insert(0, str(_FILE.parents[2]))

import streamlit as st

from app import theme
from assistant import engine, env, goldset, llm
from pipeline import config

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


if "assistant_msgs" not in st.session_state:
    st.session_state.assistant_msgs = []

with st.sidebar:
    if st.button("🧹 Clear conversation", use_container_width=True):
        st.session_state.assistant_msgs = []
        st.rerun()
    st.markdown(
        "**Try:**\n"
        "- What are total net sales all time?\n"
        "- أعلى 5 فروع مبيعاً في 2025\n"
        "- Which customers are at risk of churn?\n"
        "- Show returns by reason\n"
    )
    if goldset.GOLDSET:
        st.caption(f"Goldset coverage: {len(goldset.GOLDSET)} question/invariant pairs "
                   "run in `tests/test_goldset.py`.")

if not st.session_state.get("assistant_llm_ready"):
    with st.spinner("Connecting to the assistant LLM…"):
        st.session_state.assistant_llm_ready = llm.probe()

if not st.session_state.assistant_llm_ready:
    st.warning(
        f"The assistant LLM is not reachable at **{env.LLM_BASE_URL}** (model "
        f"`{env.LLM_MODEL}`). Start one and reload this page:\n\n```\n"
        "ollama serve\nollama pull llama3.1\n```\n\n"
        "…or point `COTTONIL_LLM_BASE_URL` at any OpenAI-compatible server in `.env`.",
        icon="🔌",
    )
    st.stop()

# -- user message -> engine -> persisted ------------------------------ -------
prompt = st.chat_input("Ask in English or Arabic…")
if prompt:
    st.session_state.assistant_msgs.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧍"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        with st.status("Querying the dataset…", expanded=False) as status:
            result = engine.ask(prompt)
            status.update(state="complete" if not result.error else "error")

        st.session_state.assistant_msgs.append({
            "role": "assistant",
            "narration": result.narration or result.error,
            "sql": result.sql, "df": result.df, "sources": result.sources,
            "truncated": result.truncated, "refusal": result.refusal,
            "attempts": result.attempts,
        })

# -- render history ---------------------------------------------------------- --
for index, message in enumerate(st.session_state.assistant_msgs):
    if message["role"] == "user":
        with st.chat_message("user", avatar="🧍"):
            st.markdown(message["content"])
        continue

    narration = message.get("narration") or ""
    refusal = message.get("refusal", False)
    with st.chat_message("assistant", avatar="🤖"):
        if refusal:
            st.warning(narration, icon="🛑")
        else:
            st.markdown(narration)

        if message.get("truncated"):
            st.info("Result truncated at 200 rows.", icon="✂️")

        if message.get("df") is not None:
            st.dataframe(message["df"], hide_index=True)

        if message.get("sql"):
            with st.expander("🔍 SQL used for this answer"):
                st.code(message["sql"], language="sql")
                attempts = message.get("attempts") or []
                if attempts:
                    st.caption("· ".join(attempts))

        deep_link = next(
            (VIEW_PAGE_MAP[s.split(".")[-1]] for s in message.get("sources", [])
             if s.split(".")[-1] in VIEW_PAGE_MAP),
            None,
        )
        if deep_link:
            st.button("📊 Open the matching dashboard", key=f"link-{index}-"
                      f"{deep_link}", on_click=st.switch_page, args=(deep_link,))
