"""OpenAI-compatible transport for the assistant (T092, Gemini-first chain).

Iterates `env.PROVIDERS` in order (defaults: Gemini primary, Groq fallback) and
returns the FIRST successful completion. Any failure on a provider — quota
exhaustion (429), auth (401/403), rate limit, outage, empty content — moves to
the next provider automatically; when every provider fails, the errors are
collected into one friendly LLMError. The engine owns its own retry loop per
question; this module only performs a single completion per provider.
"""

from __future__ import annotations

from openai import OpenAI

from assistant import env


class LLMError(RuntimeError):
    """Every configured LLM provider failed to produce an answer."""


_clients: dict[tuple[str, float], OpenAI] = {}
_last_provider: env.LLMConfig | None = None


def client(provider: env.LLMConfig | None = None, *, timeout: float | None = None) -> OpenAI:
    """Cached OpenAI-SDK client for a provider (default: the chain primary)."""
    provider = provider or (env.PROVIDERS[0] if env.PROVIDERS else None)
    if provider is None:
        raise LLMError("No assistant LLM provider is configured in `.env`.")
    key = (provider.name, timeout if timeout is not None else env.LLM_TIMEOUT)
    if key not in _clients:
        _clients[key] = OpenAI(
            base_url=provider.base_url,
            api_key=provider.api_key,
            timeout=timeout if timeout is not None else env.LLM_TIMEOUT,
            max_retries=0,  # retry/fallback logic lives here + in the engine
        )
    return _clients[key]


def last_provider() -> env.LLMConfig | None:
    """Provider that produced the most recent successful completion (or None)."""
    return _last_provider


def probe(timeout_seconds: float = 1.5) -> bool:
    """True when ANY provider in the chain answers a cheap models.list() call.

    1.5s per provider keeps the down-LLM banner snappy on the page (the perf
    budget assumes an answered endpoint)."""
    for provider in env.PROVIDERS:
        try:
            probe_client = OpenAI(base_url=provider.base_url, api_key=provider.api_key,
                                  timeout=timeout_seconds, max_retries=0)
            list(probe_client.models.list())
            return True
        except Exception:  # noqa: BLE001, S112 - probe() must return False, not raise
            continue
    return False


def describe_providers() -> list[str]:
    """Banner-friendly chain summary: 'Gemini · model (primary)', ..."""
    if not env.PROVIDERS:
        return ["none configured"]
    labels = []
    for index, provider in enumerate(env.PROVIDERS):
        role = "primary" if index == 0 else "fallback"
        labels.append(f"{provider.name} · `{provider.model}` ({role})")
    return labels


def chat(messages: list[dict[str, str]], *, temperature: float | None = None,
         max_tokens: int = 1400) -> str:
    """One chat completion from the first healthy provider in the chain.

    Raises LLMError with per-provider reasons when every provider fails."""
    if not env.PROVIDERS:
        raise LLMError(
            "No assistant LLM provider is configured. Add GEMINI_API_KEY / "
            "GROQ_API_KEY (and models) to `.env`, then reload the page."
        )
    failures: list[str] = []
    global _last_provider
    for provider in env.PROVIDERS:
        try:
            response = client(provider).chat.completions.create(
                model=provider.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=env.TEMPERATURE if temperature is None else temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - fall through to the next provider
            failures.append(f"{provider.name}: {_brief(exc)}")
            continue
        content = (response.choices[0].message.content or "").strip() if response.choices else ""
        if not content:
            failures.append(f"{provider.name}: empty completion")
            continue
        _last_provider = provider
        return content
    raise LLMError(
        "All assistant LLM providers failed — "
        + "; ".join(failures) + ". "
        + "Check the keys in `.env` (GEMINI_API_KEY, GROQ_API_KEY) and reload the page."
    )


def _brief(exc: Exception) -> str:
    """Short single-line reason for a provider failure (no stack/bar text)."""
    text = " ".join(str(exc).split())[:180]
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    reason = getattr(exc, "code", "") or getattr(exc, "type", "")
    parts = [part for part in (f"[{status}]" if status else "", str(reason), text) if part]
    return " ".join(parts) if parts else exc.__class__.__name__
