"""Assistant LLM + engine settings.

Provider chain (mirrors .env.example): the first configured provider is primary,
the rest are fallbacks used automatically when the primary fails (quota, auth,
rate limit, outage). Defaults:

- Gemini (primary):   GEMINI_API_KEY + GEMINI_MODEL, OpenAI-compatible endpoint
- Groq (fallback):    GROQ_API_KEY + GROQ_MODEL, OpenAI-compatible endpoint

Overrides (all optional, applied per role):
- COTTONIL_LLM_BASE_URL / _MODEL / _API_KEY          override the PRIMARY provider
- COTTONIL_LLM_FALLBACK_BASE_URL / _MODEL / _API_KEY override the FALLBACK provider
- COTTONIL_LLM_TIMEOUT    per-completion seconds (default 120)
- COTTONIL_SQL_TIMEOUT    DuckDB query time cap seconds (default 25)

A repo-local `.env` (gitignored) may define any of the above; real environment
variables always win. Values in `.env` may be quoted (quotes are stripped).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from pipeline import config

_DOTENV = config.BASE_DIR / ".env"

if _DOTENV.exists():
    for line in _DOTENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def _setting(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
_GROQ_BASE = "https://api.groq.com/openai/v1"


@dataclass(frozen=True)
class LLMConfig:
    """One OpenAI-compatible chat provider entry."""

    name: str
    base_url: str
    model: str
    api_key: str


def _provider(name: str, *, key_var: str, model_var: str, default_base: str,
              alt_key_var: str = "", alt_model_var: str = "",
              alt_base_var: str = "") -> LLMConfig | None:
    """Build a provider from its native vars plus the COTTONIL_LLM_* overrides."""
    api_key = _setting(key_var) or (_setting(alt_key_var) if alt_key_var else "")
    model = _setting(model_var) or (_setting(alt_model_var) if alt_model_var else "")
    base_url = (_setting(alt_base_var) if alt_base_var else "") or default_base
    if not (api_key and model):
        return None
    return LLMConfig(name=name, base_url=base_url.rstrip("/"), model=model, api_key=api_key)


PRIMARY: LLMConfig | None = _provider(
    "Gemini",
    key_var="GEMINI_API_KEY", model_var="GEMINI_MODEL", default_base=_GEMINI_BASE,
    alt_key_var="COTTONIL_LLM_API_KEY", alt_model_var="COTTONIL_LLM_MODEL",
    alt_base_var="COTTONIL_LLM_BASE_URL",
)
FALLBACK: LLMConfig | None = _provider(
    "Groq",
    key_var="GROQ_API_KEY", model_var="GROQ_MODEL", default_base=_GROQ_BASE,
    alt_key_var="COTTONIL_LLM_FALLBACK_API_KEY",
    alt_model_var="COTTONIL_LLM_FALLBACK_MODEL",
    alt_base_var="COTTONIL_LLM_FALLBACK_BASE_URL",
)

PROVIDERS: list[LLMConfig] = [p for p in (PRIMARY, FALLBACK) if p is not None]
"""Ordered provider chain: index 0 is primary, the rest are automatic fallbacks."""

LLM_TIMEOUT = float(_setting("COTTONIL_LLM_TIMEOUT") or 120)
SQL_TIMEOUT = float(_setting("COTTONIL_SQL_TIMEOUT") or 25)
TEMPERATURE = float(_setting("COTTONIL_LLM_TEMPERATURE") or 0.1)

MAX_ROWS = 200          # assistant result cap before the page trims display
NARRATE_ROWS = 30       # rows fed back into the narration prompt
SQL_RETRIES = 2         # LLM retries after a validation/execution failure (T092)
