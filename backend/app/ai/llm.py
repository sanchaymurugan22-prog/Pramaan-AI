"""The ONE place in Pramaan AI that talks to the language model.

Both providers speak the OpenAI-style "chat completions" API:
  - AI_MODE=local -> llama.cpp `llama-server` on this computer (Sarvam 30B GGUF)
  - AI_MODE=cloud -> Sarvam AI hosted API (development fallback only)
    Docs: https://docs.sarvam.ai/api-reference/chat/chat-completions-v1
    POST {SARVAM_BASE_URL}/chat/completions, header `api-subscription-key`.

The rest of the app just calls `chat(...)` and never needs to know which
provider is in use.
"""

import re

import httpx

from app.config import settings


class LLMError(Exception):
    """Raised with a friendly, human-readable message when the LLM call fails."""


def _provider() -> tuple[str, str, dict[str, str]]:
    """Return (base_url, model, headers) for the configured AI_MODE."""
    if settings.ai_mode == "cloud":
        if not settings.sarvam_api_key:
            raise LLMError(
                "AI_MODE is 'cloud' but SARVAM_API_KEY is empty. "
                "Add your key to the .env file, or set AI_MODE=local."
            )
        headers = {"api-subscription-key": settings.sarvam_api_key}
        return settings.sarvam_base_url, settings.sarvam_model, headers

    if settings.ai_mode != "local":
        raise LLMError(f"Unknown AI_MODE '{settings.ai_mode}'. Use 'local' or 'cloud'.")

    return settings.llm_base_url, settings.llm_model, {}


# Sarvam 30B is a "thinking" model: by default it writes a long hidden reasoning
# before answering, which is very slow on a laptop CPU (~4 tokens/second).
# Pre-filling the assistant turn with an empty think block makes it answer directly.
NO_THINK_PREFILL = "<think></think>"
THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def chat(messages: list[dict], max_tokens: int = 256, temperature: float = 0.2, think: bool = False) -> str:
    """Send chat messages to the LLM and return the reply text.

    messages: [{"role": "system" | "user" | "assistant", "content": "..."}]
    max_tokens: keep this small for short outputs; the local model is slow.
    think: let the local model reason step by step first (slower, needs more max_tokens).
    """
    base_url, model, headers = _provider()
    url = base_url.rstrip("/") + "/chat/completions"

    if settings.ai_mode == "local" and not think:
        messages = messages + [{"role": "assistant", "content": NO_THINK_PREFILL}]

    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        # Wait up to LLM_TIMEOUT_SECONDS (default 600) for the reply: the local model is slow
        # (~1.4 tokens/second on the dev Intel Mac). Connecting should be instant, so fail fast
        # after 10 seconds if the server is not there.
        timeout = httpx.Timeout(settings.llm_timeout_seconds, connect=10.0)
        response = httpx.post(url, json=body, headers=headers, timeout=timeout)
    except httpx.ConnectError:
        if settings.ai_mode == "local":
            raise LLMError(
                f"Could not reach the local AI server at {base_url}. "
                "Is llama-server running? Start it and try again."
            )
        raise LLMError(f"Could not reach the Sarvam API at {base_url}. Check your internet connection.")
    except httpx.TimeoutException:
        raise LLMError(
            f"The AI server took longer than {settings.llm_timeout_seconds:.0f} seconds to reply. "
            "Try again, or raise LLM_TIMEOUT_SECONDS in .env."
        )
    except httpx.HTTPError as exc:
        raise LLMError(f"Error talking to the AI server: {exc}")

    if response.status_code in (401, 403):
        raise LLMError("The AI server rejected the API key. Check SARVAM_API_KEY in .env.")
    if response.status_code >= 400:
        raise LLMError(f"The AI server returned an error ({response.status_code}): {response.text[:300]}")

    try:
        data = response.json()
        choice = data["choices"][0]
        content = choice["message"].get("content") or ""
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise LLMError("The AI server sent a reply in an unexpected format.")

    # Remove any think block (the pre-fill is echoed back by llama.cpp)
    content = THINK_BLOCK.sub("", content).strip()

    if not content and choice.get("finish_reason") == "length":
        raise LLMError(
            f"The model used up all {max_tokens} tokens before giving an answer "
            "(it was probably still thinking). Try a larger max_tokens."
        )
    return content


def describe() -> dict:
    """Which provider and model are configured (safe to show in the UI; no secrets)."""
    try:
        base_url, model, _ = _provider()
    except LLMError:
        base_url, model = "", ""
    return {"ai_mode": settings.ai_mode, "model": model, "base_url": base_url}
