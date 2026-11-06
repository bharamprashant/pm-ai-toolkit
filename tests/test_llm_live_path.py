"""The live-model call path, tested with a fake SDK (no network, no key).

Regression: the first real run failed with "unexpected keyword argument 'temperature'".
"""
import sys
import types

from core.llm import AnthropicLLM


class _Messages:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        if "temperature" in kwargs:
            raise TypeError("Messages.create() got an unexpected keyword argument 'temperature'")
        self.kwargs = kwargs
        block = types.SimpleNamespace(type="text", text='{"rag": "GREEN", "reason": "ok", "keys": []}')
        return types.SimpleNamespace(content=[block])


def _install_fake(monkeypatch):
    msgs = _Messages()
    fake = types.SimpleNamespace(Anthropic=lambda: types.SimpleNamespace(messages=msgs))
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")
    return msgs


def test_live_call_sends_no_temperature_and_parses_json(monkeypatch):
    msgs = _install_fake(monkeypatch)
    out = AnthropicLLM().complete_json("sys", "user text")
    assert out["rag"] == "GREEN"
    assert "temperature" not in msgs.kwargs
    assert msgs.kwargs["messages"][0]["content"] == "user text"
    assert "ONLY one JSON object" in msgs.kwargs["system"]


def test_live_requires_key(monkeypatch):
    import pytest
    _install_fake(monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(RuntimeError):
        AnthropicLLM()
