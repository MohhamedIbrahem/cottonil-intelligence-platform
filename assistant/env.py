"""Assistant LLM + engine settings.

Env contract (mirrors .env.example):
- COTTONIL_LLM_BASE_URL   OpenAI-compatible endpoint; default local Ollama /v1
- COTTONIL_LLM_MODEL      model name; default llama3.1 (see README for Arabic-tuned options)
- COTTONIL_LLM_API_KEY    only needed for cloud providers ("ollama" works as a dummy key)
- COTTONIL_LLM_TIMEOUT    per-completion seconds (default 120)
- COTTONIL_SQL_TIMEOUT    DuckDB query time cap seconds (default 25)

A repo-local `.env` (gitignored) may override any of the above; real environment
variables always win.
"""

from __future__ import annotations

import os

from pipeline import config

_DOTENV = config.BASE_DIR / ".env"

if _DOTENV.exists():
    for line in _DOTENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

LLM_BASE_URL = (os.environ.get("COTTONIL_LLM_BASE_URL") or "http://localhost:11434/v1").strip()
LLM_MODEL = (os.environ.get("COTTONIL_LLM_MODEL") or "llama3.1").strip()
LLM_API_KEY = (os.environ.get("COTTONIL_LLM_API_KEY") or "ollama").strip()
LLM_TIMEOUT = float(os.environ.get("COTTONIL_LLM_TIMEOUT") or 120)
SQL_TIMEOUT = float(os.environ.get("COTTONIL_SQL_TIMEOUT") or 25)
TEMPERATURE = float(os.environ.get("COTTONIL_LLM_TEMPERATURE") or 0.1)

MAX_ROWS = 200          # assistant result cap before the page trims display
NARRATE_ROWS = 30       # rows fed back into the narration prompt
SQL_RETRIES = 2         # LLM retries after a validation/execution failure (T092)
