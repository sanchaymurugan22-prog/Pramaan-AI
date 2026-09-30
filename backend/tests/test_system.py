"""Tests for the health check and AI ping routes.

Run (from the backend/ folder):  .venv/bin/python -m pytest
"""

from fastapi.testclient import TestClient

from app.ai import llm
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["ai_mode"] in ("local", "cloud")


def test_ai_ping_success(monkeypatch):
    # Pretend the LLM answered, so this test does not need llama-server running
    monkeypatch.setattr(llm, "chat", lambda messages, max_tokens=256: "Namaste")
    body = client.get("/api/ai/ping").json()
    assert body["ok"] is True
    assert body["reply"] == "Namaste"


def test_ai_ping_friendly_error(monkeypatch):
    def fail(messages, max_tokens=256):
        raise llm.LLMError("Could not reach the local AI server.")

    monkeypatch.setattr(llm, "chat", fail)
    body = client.get("/api/ai/ping").json()
    assert body["ok"] is False
    assert "Could not reach" in body["error"]


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self._data


def test_chat_strips_think_block(monkeypatch):
    sent = {}

    def fake_post(url, json, headers, timeout):
        sent["messages"] = json["messages"]
        return FakeResponse({"choices": [{"finish_reason": "stop", "message": {"content": "<think></think>\nNamaste."}}]})

    monkeypatch.setattr(llm.settings, "ai_mode", "local")
    monkeypatch.setattr(llm.httpx, "post", fake_post)
    assert llm.chat([{"role": "user", "content": "hi"}]) == "Namaste."
    # local mode adds the empty think block so the model answers directly
    assert sent["messages"][-1] == {"role": "assistant", "content": llm.NO_THINK_PREFILL}


def test_chat_ran_out_of_tokens(monkeypatch):
    def fake_post(url, json, headers, timeout):
        return FakeResponse({"choices": [{"finish_reason": "length", "message": {"content": ""}}]})

    monkeypatch.setattr(llm.settings, "ai_mode", "local")
    monkeypatch.setattr(llm.httpx, "post", fake_post)
    try:
        llm.chat([{"role": "user", "content": "hi"}], max_tokens=8)
        assert False, "expected LLMError"
    except llm.LLMError as exc:
        assert "8 tokens" in str(exc)
