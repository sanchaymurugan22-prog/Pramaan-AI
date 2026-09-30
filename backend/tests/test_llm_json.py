"""Tests for getting JSON out of the LLM: schema mode, fallback, retry, and cut-off answers.

The model is never called: httpx.post is replaced with a fake that returns what we want.
"""

import json

import pytest

from app.ai import llm

SCHEMA = {"type": "object", "properties": {"tweets": {"type": "array"}}, "required": ["tweets"]}
MESSAGES = [{"role": "system", "content": "sys"}, {"role": "user", "content": "Write a thread."}]


class FakeResponse:
    """A pretend server reply. Works as a normal reply and as a streamed one."""

    def __init__(self, content="", status_code=200, finish_reason="stop"):
        self.content = content
        self.status_code = status_code
        self.finish_reason = finish_reason
        self.text = content if status_code != 200 else ""

    # normal reply
    def json(self):
        return {"choices": [{"finish_reason": self.finish_reason, "message": {"content": self.content}}], "usage": {"completion_tokens": 7}}

    # streamed reply: the text in small pieces, then the finish reason, then [DONE]
    def iter_lines(self):
        yield "data: " + json.dumps({"choices": [], "prompt_progress": {"total": 100, "cache": 20, "processed": 30}})
        for i in range(0, len(self.content), 5):
            yield "data: " + json.dumps({"choices": [{"delta": {"content": self.content[i : i + 5]}, "finish_reason": None}]})
        yield "data: " + json.dumps({"choices": [{"delta": {}, "finish_reason": self.finish_reason}]})
        yield "data: [DONE]"

    def read(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_server(monkeypatch, replies):
    """Make the server return `replies` one after another. Returns the list of request bodies sent."""
    sent = []

    def fake_post(url, json, headers, timeout):
        sent.append(json)
        return replies.pop(0)

    def fake_stream(method, url, json, headers, timeout):
        sent.append(json)
        return replies.pop(0)

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    monkeypatch.setattr(llm.httpx, "stream", fake_stream)
    return sent


@pytest.fixture
def local_mode(monkeypatch):
    monkeypatch.setattr(llm.settings, "ai_mode", "local")
    monkeypatch.setattr(llm, "_schema_supported", None)


# ---- finding JSON in text -----------------------------------------------------------------


def test_extract_json_ignores_extra_words_and_fences():
    text = 'Sure! Here it is:\n```json\n{"a": 1, "b": "x}y"}\n```\nHope that helps.'
    assert llm.extract_json(text) == {"a": 1, "b": "x}y"}


def test_extract_json_fixes_trailing_commas():
    assert llm.extract_json('{"a": [1, 2,], }') == {"a": [1, 2]}


def test_extract_json_returns_none_without_json():
    assert llm.extract_json("I cannot help with that.") is None


def test_repair_truncated_json_drops_the_half_written_item():
    cut = '{"tweets": [{"text": "one", "fact_ids": ["F1"]}, {"text": "two is half writ'
    assert llm.repair_truncated_json(cut) == {"tweets": [{"text": "one", "fact_ids": ["F1"]}]}


# ---- chat_json ----------------------------------------------------------------------------


def test_mock_mode_returns_canned_answer(monkeypatch):
    monkeypatch.setattr(llm.settings, "ai_mode", "mock")
    reply = llm.chat_json(MESSAGES, SCHEMA, kind="x_thread", max_tokens=100)
    assert len(reply.data["tweets"]) >= 2
    assert reply.truncated is False


def test_local_mode_sends_the_schema(monkeypatch, local_mode):
    sent = fake_server(monkeypatch, [FakeResponse('{"tweets": []}')])
    reply = llm.chat_json(MESSAGES, SCHEMA, kind="x_thread", max_tokens=100)
    assert reply.data == {"tweets": []}
    body = sent[0]
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["messages"] == MESSAGES  # no think pre-fill together with a schema
    assert body["max_tokens"] == 100
    assert body["stream"] is True  # local answers are streamed


def test_streaming_reports_progress(monkeypatch, local_mode):
    fake_server(monkeypatch, [FakeResponse('{"tweets": ["a fairly long first tweet"]}')])
    notes = []
    reply = llm.chat_json(MESSAGES, SCHEMA, kind="x_thread", max_tokens=100, on_progress=notes.append)
    assert reply.data == {"tweets": ["a fairly long first tweet"]}
    assert notes[0] == "reading the prompt 50%"
    assert notes[-1] == f"{reply.tokens} tokens written" and reply.tokens > 1


def test_request_asks_for_prompt_progress(monkeypatch, local_mode):
    sent = fake_server(monkeypatch, [FakeResponse('{"tweets": []}')])
    llm.chat_json(MESSAGES, SCHEMA, kind="x_thread", max_tokens=100)
    assert sent[0]["return_progress"] is True


def test_server_error_in_the_middle_of_a_stream(monkeypatch, local_mode):
    class Broken(FakeResponse):
        def iter_lines(self):
            yield 'data: {"error": {"message": "out of memory"}}'

    fake_server(monkeypatch, [Broken()])
    with pytest.raises(llm.LLMError, match="out of memory"):
        llm.chat_json(MESSAGES, SCHEMA, kind="x_thread", max_tokens=100)


def test_falls_back_when_server_has_no_schema_support(monkeypatch, local_mode):
    sent = fake_server(monkeypatch, [FakeResponse("bad", status_code=400), FakeResponse('{"tweets": ["x"]}')])
    reply = llm.chat_json(MESSAGES, SCHEMA, kind="x_thread", max_tokens=100)
    assert reply.data == {"tweets": ["x"]}
    assert "response_format" not in sent[1]
    assert sent[1]["messages"][-1] == {"role": "assistant", "content": llm.NO_THINK_PREFILL}
    assert llm._schema_supported is False


def test_retries_once_when_reply_is_not_json(monkeypatch, local_mode):
    monkeypatch.setattr(llm, "_schema_supported", False)
    sent = fake_server(monkeypatch, [FakeResponse("Here are some tweets..."), FakeResponse('{"tweets": []}')])
    reply = llm.chat_json(MESSAGES, SCHEMA, kind="x_thread", max_tokens=100)
    assert reply.data == {"tweets": []}
    assert len(sent) == 2
    assert llm.JSON_REMINDER in sent[1]["messages"][1]["content"]
    assert sent[1]["temperature"] == 0.0


def test_gives_up_after_one_retry(monkeypatch, local_mode):
    monkeypatch.setattr(llm, "_schema_supported", False)
    fake_server(monkeypatch, [FakeResponse("nope"), FakeResponse("still nope")])
    with pytest.raises(llm.LLMError, match="valid JSON"):
        llm.chat_json(MESSAGES, SCHEMA, kind="x_thread", max_tokens=100)


def test_cut_off_answer_is_rescued_and_marked(monkeypatch, local_mode):
    cut = '{"tweets": [{"text": "one"}, {"text": "tw'
    fake_server(monkeypatch, [FakeResponse(cut, finish_reason="length")])
    reply = llm.chat_json(MESSAGES, SCHEMA, kind="x_thread", max_tokens=100)
    assert reply.truncated is True
    assert reply.data == {"tweets": [{"text": "one"}]}
