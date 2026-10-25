"""OpenAI-compatible transport for the assistant (T092).

Thin client over the `openai` SDK configured for any OpenAI-compatible endpoint;
defaults to a local Ollama server (no API key). The engine owns retry logic -
this module only performs a single completion and converts every failure into a
friendly LLMError with setup hints.
"""

from __future__ import annotations

from openai import OpenAI

from assistant import env


class LLMError(RuntimeError):
    """The LLM endpoint could not be reached or misbehaved."""


_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=env.LLM_BASE_URL,
            api_key=env.LLM_API_KEY,
            timeout=env.LLM_TIMEOUT,
            max_retries=0,  # the engine handles retries explicitly
        )
    return _client


def probe(timeout_seconds: float = 4.0) -> bool:
    """True when the configured endpoint answers a cheap models.list() call."""
    try:
        probe_client = OpenAI(base_url=env.LLM_BASE_URL, api_key=env.LLM_API_KEY,
                              timeout=timeout_seconds, max_retries=0)
        list(probe_client.models.list())
        return True
    except Exception:  # noqa: BLE001 - probe() must return False, not raise
        return False


def chat(messages: list[dict[str, str]], *, temperature: float | None = None,
         max_tokens: int = 1400) -> str:
    """One chat completion; raises LLMError with setup hints when unreachable."""
    try:
        response = client().chat.completions.create(
            model=env.LLM_MODEL,
            messages=messages,  # type: ignore[arg-type]
            temperature=env.TEMPERATURE if temperature is None else temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:  # openai wraps many error types; convert uniformly
        raise LLMError(
            f"Cannot reach the LLM at {env.LLM_BASE_URL} "
            f"(model '{env.LLM_MODEL}'). For local use: start Ollama "
            "(`ollama serve`) and pull a model (`ollama pull llama3.1`), or point "
            "COTTONIL_LLM_BASE_URL at any OpenAI-compatible server."
        ) from exc
    content = (response.choices[0].message.content or "").strip() if response.choices else ""
    if not content:
        raise LLMError("The LLM returned an empty completion.")
    return content
