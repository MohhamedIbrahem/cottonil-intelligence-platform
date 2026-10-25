"""Cottonil AI assistant: read-only, DuckDB-grounded answer engine (deck p.23).

Modules:
- env          LLM + engine settings (env contract: COTTONIL_LLM_*, COTTONIL_SQL_TIMEOUT)
- schema_docs  prompt-ready view catalog from the live database (T090)
- sql_guard    SELECT-only / single-statement / allowlist / row-limit enforcement (T091)
- llm          OpenAI-compatible transport (default Ollama) (T092)
- prompts      system prompts: schema (from schema_docs) + contract + refusal policy (T093)
- engine       question -> SQL -> guarded execution -> grounded narrative
- goldset      question/invariant pairs for local accuracy checks (T095)
"""
