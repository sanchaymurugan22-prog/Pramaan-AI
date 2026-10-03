"""The ONE place in Pramaan AI that talks to the language model.

Three modes, set by AI_MODE in .env:
  - local -> llama.cpp `llama-server` on this computer (Sarvam 30B GGUF)
  - cloud -> Sarvam AI hosted API (development fallback only)
    Docs: https://docs.sarvam.ai/api-reference/chat/chat-completions-v1
    POST {SARVAM_BASE_URL}/chat/completions, header `api-subscription-key`.
  - mock  -> no model at all: instant answers built from the (masked) text it is sent
    (app/ai/mock_ai.py), for testing the UI and for the automated tests.

Local and cloud both speak the OpenAI-style "chat completions" API.

The rest of the app calls `chat(...)` for plain text or `chat_json(...)` for a JSON
answer, and never needs to know which mode is in use.
"""

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from app.ai import mock_ai
from app.config import settings


class LLMError(Exception):
    """Raised with a friendly, human-readable message when the LLM call fails."""


class _BadRequest(LLMError):
    """The server said our request was wrong (HTTP 400), e.g. it does not support JSON schemas."""


def _provider() -> tuple[str, str, dict[str, str]]:
    """Return (base_url, model, headers) for the configured AI_MODE."""
    if settings.ai_mode == "mock":
        return "mock", "mock (answers built from the source)", {}

    if settings.ai_mode == "cloud":
        if not settings.sarvam_api_key:
            raise LLMError(
                "AI_MODE is 'cloud' but SARVAM_API_KEY is empty. "
                "Add your key to the .env file, or set AI_MODE=local."
            )
        headers = {"api-subscription-key": settings.sarvam_api_key}
        return settings.sarvam_base_url, settings.sarvam_model, headers

    if settings.ai_mode != "local":
        raise LLMError(f"Unknown AI_MODE '{settings.ai_mode}'. Use 'local', 'cloud' or 'mock'.")

    return settings.llm_base_url, settings.llm_model, {}


# Sarvam 30B is a "thinking" model: by default it writes a long hidden reasoning
# before answering, which is very slow on a laptop CPU (~1.4 tokens/second).
# Pre-filling the assistant turn with an empty think block makes it answer directly.
NO_THINK_PREFILL = "<think></think>"
THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def _post(body: dict, stream: bool = False, on_progress: Callable[[str], None] | None = None) -> tuple[str, str, dict]:
    """Send one chat request. Returns (reply text, finish_reason, usage). Raises LLMError.

    stream=True asks the server to send the answer token by token. We still return the whole
    answer at the end, but: (1) the timeout then only applies to the gap between messages from the
    server, not to the whole answer (a long answer can take over 10 minutes on the slow laptop), and
    (2) on_progress is called with a short note like "reading the prompt 40%" or "57 tokens written",
    for the progress display.
    """
    base_url, model, headers = _provider()
    url = base_url.rstrip("/") + "/chat/completions"
    body = {"model": model, **body}

    try:
        # Wait up to LLM_TIMEOUT_SECONDS (default 600) for the reply (or, when streaming, for the
        # next token): the local model is slow (~1.4 tokens/second on the dev Intel Mac) and first
        # has to read the whole prompt. Connecting should be instant, so fail fast after 10 seconds
        # if the server is not there.
        timeout = httpx.Timeout(settings.llm_timeout_seconds, connect=10.0)
        if stream:
            content, finish_reason, usage = _read_stream(url, body, headers, timeout, on_progress)
        else:
            response = httpx.post(url, json=body, headers=headers, timeout=timeout)
            _check_status(response.status_code, response.text)
            content, finish_reason, usage = _read_reply(response)
    except httpx.ConnectError:
        if settings.ai_mode == "local":
            raise LLMError(
                f"Could not reach the local AI server at {base_url}. "
                "Is llama-server running? Start it with scripts/start-ai.sh and try again."
            )
        raise LLMError(f"Could not reach the Sarvam API at {base_url}. Check your internet connection.")
    except httpx.TimeoutException:
        raise LLMError(
            f"The AI server took longer than {settings.llm_timeout_seconds:.0f} seconds to reply. "
            "Try again, or raise LLM_TIMEOUT_SECONDS in .env."
        )
    except httpx.HTTPError as exc:
        raise LLMError(f"Error talking to the AI server: {exc}")

    # Remove any think block (the pre-fill is echoed back by llama.cpp)
    content = THINK_BLOCK.sub("", content).strip()
    return content, finish_reason, usage


def _check_status(status_code: int, text: str) -> None:
    if status_code in (401, 403):
        raise LLMError("The AI server rejected the API key. Check SARVAM_API_KEY in .env.")
    if status_code == 400:
        raise _BadRequest(f"The AI server did not accept the request: {text[:300]}")
    if status_code >= 400:
        raise LLMError(f"The AI server returned an error ({status_code}): {text[:300]}")


def _read_reply(response) -> tuple[str, str, dict]:
    """A normal (not streamed) reply."""
    try:
        data = response.json()
        choice = data["choices"][0]
        content = choice["message"].get("content") or ""
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise LLMError("The AI server sent a reply in an unexpected format.")
    return content, choice.get("finish_reason") or "", data.get("usage") or {}


def _read_stream(url, body, headers, timeout, on_progress) -> tuple[str, str, dict]:
    """A streamed reply: lines of 'data: {json}', each with the next piece of text, then 'data: [DONE]'."""
    parts: list[str] = []
    finish_reason, usage = "", {}
    # return_progress: llama.cpp also reports how far it is with reading the prompt. Reading a long
    # prompt takes minutes on the laptop; these reports keep the connection from timing out.
    body = {**body, "stream": True, "return_progress": True}
    with httpx.stream("POST", url, json=body, headers=headers, timeout=timeout) as response:
        if response.status_code >= 400:
            response.read()
            _check_status(response.status_code, response.text)
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except ValueError:
                continue
            if "error" in chunk:
                raise LLMError(f"The AI server stopped with an error: {str(chunk['error'])[:300]}")
            usage = chunk.get("usage") or usage
            reading = chunk.get("prompt_progress")
            if reading and on_progress and reading.get("total"):
                done = reading.get("processed", 0) + reading.get("cache", 0)
                on_progress(f"reading the prompt {min(100, round(100 * done / reading['total']))}%")
            for choice in chunk.get("choices") or []:
                text = (choice.get("delta") or {}).get("content")
                if text:
                    parts.append(text)
                    if on_progress:
                        on_progress(f"{len(parts)} tokens written")  # llama.cpp sends about one token per piece
                finish_reason = choice.get("finish_reason") or finish_reason
    if "completion_tokens" not in usage:
        usage = {**usage, "completion_tokens": len(parts)}
    return "".join(parts), finish_reason, usage


def chat(messages: list[dict], max_tokens: int = 256, temperature: float = 0.2, think: bool = False) -> str:
    """Send chat messages to the LLM and return the reply text.

    messages: [{"role": "system" | "user" | "assistant", "content": "..."}]
    max_tokens: keep this small for short outputs; the local model is slow.
    think: let the local model reason step by step first (slower, needs more max_tokens).
    """
    if settings.ai_mode == "mock":
        _mock_wait()
        return "Namaste (mock AI)"

    if settings.ai_mode in ("local", "cloud") and not think:
        messages = messages + [{"role": "assistant", "content": NO_THINK_PREFILL}]

    content, finish_reason, _ = _post({"messages": messages, "max_tokens": max_tokens, "temperature": temperature})

    if not content and finish_reason == "length":
        raise LLMError(
            f"The model used up all {max_tokens} tokens before giving an answer "
            "(it was probably still thinking). Try a larger max_tokens."
        )
    return content


# ---------------------------------------------------------------------------
# JSON answers
# ---------------------------------------------------------------------------


@dataclass
class JsonReply:
    data: dict             # the parsed JSON object
    truncated: bool        # True if the model hit max_tokens and we closed the JSON ourselves
    seconds: float         # how long the model took
    tokens: int | None     # how many tokens the model wrote (if the server told us)


# Does the local llama-server accept a JSON schema? None = not tried yet.
# Recent llama.cpp builds do: the schema is turned into a grammar, so the model *cannot*
# write anything except JSON of that shape. Older builds answer HTTP 400; then we fall back.
_schema_supported: bool | None = None

JSON_REMINDER = (
    "Your previous answer was not valid JSON. Reply again with ONLY the JSON object: "
    "no explanation, no markdown, no code fences."
)


def chat_json(
    messages: list[dict],
    schema: dict,
    kind: str,
    max_tokens: int,
    temperature: float = 0.2,
    on_progress: Callable[[str], None] | None = None,
) -> JsonReply:
    """Ask the LLM for a JSON object shaped like `schema` and return it parsed.

    kind: what we are asking for ("factsheet", "x_thread", ...). Only mock mode uses it,
          to know which answer to build from the messages.
    on_progress: called with short notes like "57 tokens written" (local mode streams the answer).

    How we make sure we get valid JSON:
      1. local mode: send the schema, so llama.cpp forces valid JSON of that shape;
      2. otherwise: find the JSON object in the reply text (ignoring extra words, code fences);
      3. if that still fails, ask once more with a stricter reminder;
      4. if the answer was cut off at max_tokens, close the open brackets ourselves
         and mark the reply as truncated (better than throwing away minutes of work).
    """
    if settings.ai_mode == "mock":
        started = time.monotonic()
        _mock_wait()
        return JsonReply(mock_ai.answer(kind, messages), False, round(time.monotonic() - started, 2), None)

    started = time.monotonic()
    data, truncated, tokens = _ask_json(messages, schema, max_tokens, temperature, on_progress)
    if not isinstance(data, dict):
        data = None
    if data is None:
        # One retry, colder and with a reminder
        retry_messages = messages[:-1] + [
            {"role": messages[-1]["role"], "content": messages[-1]["content"] + "\n\n" + JSON_REMINDER}
        ]
        data, truncated, tokens = _ask_json(retry_messages, schema, max_tokens, 0.0, on_progress)
        if not isinstance(data, dict):
            data = None
    if data is None:
        raise LLMError("The model did not return valid JSON, even after one retry. Try again.")

    if data:
        missing = [key for key in schema.get("required", []) if key not in data]
        if missing:
            if "tweets" in missing:
                for alias in ("x_thread", "thread", "posts", "items", "data"):
                    if alias in data and isinstance(data[alias], list):
                        data["tweets"] = data.pop(alias)
                        break
            if "paragraphs" in missing:
                for alias in ("posts", "post", "content", "body", "items", "sections"):
                    if alias in data:
                        val = data.pop(alias)
                        if isinstance(val, list):
                            data["paragraphs"] = val
                        elif isinstance(val, str):
                            data["paragraphs"] = [{"text": val, "fact_ids": []}]
                        break

    missing = [key for key in schema.get("required", []) if key not in data]
    if missing and not truncated:
        raise LLMError(f"The model's answer is missing: {', '.join(missing)}. Try again.")

    return JsonReply(data, truncated, round(time.monotonic() - started, 1), tokens)


def _ask_json(messages, schema, max_tokens, temperature, on_progress=None) -> tuple[dict | None, bool, int | None]:
    """One request. Returns (parsed JSON or None, truncated, tokens written)."""
    global _schema_supported

    body: dict = {"max_tokens": max_tokens, "temperature": temperature}
    if settings.ai_mode == "local":
        # llama.cpp keeps the processed prompt in memory, so the next request that starts with the
        # same text (the fact sheet) skips re-reading it. On by default; set here to be explicit.
        body["cache_prompt"] = True
    use_schema = settings.ai_mode == "local" and _schema_supported is not False
    # Stream from the local server (see _post). The cloud API is used without streaming.
    stream = settings.ai_mode == "local"

    if use_schema:
        # With a schema the empty-think pre-fill confuses llama.cpp, so switch thinking off
        # through the chat template instead.
        body.update(
            messages=messages,
            response_format={"type": "json_schema", "json_schema": {"name": "answer", "schema": schema}},
            chat_template_kwargs={"enable_thinking": False},
        )
        try:
            content, finish_reason, usage = _post(body, stream, on_progress)
            _schema_supported = True
        except _BadRequest:
            if _schema_supported:  # it worked before, so this 400 is about something else
                raise
            _schema_supported = False
            return _ask_json(messages, schema, max_tokens, temperature, on_progress)
    else:
        if settings.ai_mode in ("local", "cloud"):
            messages = messages + [{"role": "assistant", "content": NO_THINK_PREFILL}]
        body["messages"] = messages
        content, finish_reason, usage = _post(body, stream, on_progress)

    tokens = usage.get("completion_tokens")
    data = extract_json(content)
    if data is not None:
        return data, False, tokens
    if finish_reason == "length":
        data = repair_truncated_json(content)
        if data is not None:
            return data, True, tokens
        raise LLMError(
            f"The answer was cut off at {max_tokens} tokens before any usable JSON was written. "
            "Raise the MAX_TOKENS_... value for this output in .env."
        )
    return None, False, tokens


def _strip_fences(text: str) -> str:
    text = THINK_BLOCK.sub("", text)
    return re.sub(r"```(?:json)?", "", text)


def extract_json(text: str) -> dict | None:
    """Find the first complete JSON object in `text` and parse it. None if there isn't one."""
    text = _strip_fences(text)
    start = text.find("{")
    while start != -1:
        end = _matching_brace(text, start)
        if end is None:
            return None  # unfinished object (probably cut off)
        candidate = text[start : end + 1]
        for attempt in (candidate, re.sub(r",\s*([}\]])", r"\1", candidate)):  # 2nd: drop trailing commas
            try:
                value = json.loads(attempt)
                if isinstance(value, dict):
                    return value
            except ValueError:
                pass
        start = text.find("{", start + 1)
    return None


def _matching_brace(text: str, start: int) -> int | None:
    """Index of the } that closes the { at `start`, skipping braces inside strings."""
    depth, in_string, escaped = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return i
    return None


def repair_truncated_json(text: str) -> dict | None:
    """Rescue a JSON object that was cut off in the middle.

    Tries cutting back to the last few commas (dropping the half-written item) and then closing
    every open bracket; as a last resort, closes the half-written string as it is.
    """
    text = _strip_fences(text)
    start = text.find("{")
    if start == -1:
        return None
    s = text[start:]

    stack: list[str] = []      # closing brackets we still owe
    cuts: list[tuple[int, str]] = []  # (position of a comma, closers needed if we cut there)
    in_string = escaped = False
    for i, ch in enumerate(s):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack:
                stack.pop()
        elif ch == ",":
            cuts.append((i, "".join(reversed(stack))))

    candidates = [s[:i] + closers for i, closers in reversed(cuts[-20:])]
    candidates.append(s + ('"' if in_string else "") + "".join(reversed(stack)))
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except ValueError:
            pass
    return None


def _mock_wait() -> None:
    if settings.mock_delay_seconds > 0:
        time.sleep(settings.mock_delay_seconds)


def describe() -> dict:
    """Which provider and model are configured (safe to show in the UI; no secrets)."""
    try:
        base_url, model, _ = _provider()
    except LLMError:
        base_url, model = "", ""
    return {"ai_mode": settings.ai_mode, "model": model, "base_url": base_url}
