"""Cottonil AI assistant: read-only, DuckDB-grounded answer engine (deck p.23).

Modules:
- env          LLM chain + engine settings (GEMINI_*/GROQ_* keys, COTTONIL_* overrides)
- schema_docs  prompt-ready view catalog from the live database (T090)
- sql_guard    SELECT-only / single-statement / allowlist / row-limit enforcement (T091)
- llm          OpenAI-compatible transport: Gemini primary + Groq fallback chain (T092)
- prompts      system prompts: schema (from schema_docs) + contract + refusal policy (T093)
- engine       question -> SQL -> guarded execution -> grounded narrative
- goldset      question/invariant pairs for local accuracy checks (T095)
"""
