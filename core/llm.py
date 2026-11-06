"""Provider-agnostic LLM interface.

Every module talks to an `LLM` object with one method, `complete_json`.
Two implementations ship with the toolkit:

* `OfflineBaseline` - deterministic, no network, no key. It is the *baseline*
  every module is evaluated against, and it lets anyone run the repo in CI.
* `AnthropicLLM` - calls the Anthropic Messages API. Needs `pip install anthropic`
  and ANTHROPIC_API_KEY in the environment. The key is never written to disk or logs.

Design rule: the model never receives raw credentials and never writes to a
system of record. It returns JSON that our code validates.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Protocol


class LLM(Protocol):
    name: str

    def complete_json(self, system: str, user: str) -> dict[str, Any]: ...


def extract_json(text: str) -> dict[str, Any]:
    """Parse the first JSON object in a model reply (models sometimes wrap it in prose)."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("model reply contained no JSON object")
    return json.loads(match.group(0))


class OfflineBaseline:
    """Deterministic stand-in. Wraps a module-supplied function so a module can
    define its own rule-based baseline while using the same call path as a real model."""

    name = "offline-baseline"

    def __init__(self, fn: Callable[[str, str], dict[str, Any]]):
        self._fn = fn

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        return self._fn(system, user)


class AnthropicLLM:
    """Real model. Model id comes from PM_AI_MODEL so nothing is hard-wired."""

    def __init__(self, model: str | None = None, max_tokens: int = 1500):
        try:
            import anthropic  # imported lazily so the offline path needs no dependency
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("pip install anthropic to use the live model") from exc
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.Anthropic()
        self.model = model or os.environ.get("PM_AI_MODEL", "claude-sonnet-5-5")
        self.max_tokens = max_tokens
        self.name = f"anthropic:{self.model}"

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        # No temperature argument: current Claude models reject it (found on the first live run), so
        # sampling is left at the model's default and results can differ slightly between runs.
        reply = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system + "\nReturn ONLY one JSON object. No prose.",
            messages=[{"role": "user", "content": user}],
        )
        return extract_json("".join(b.text for b in reply.content if b.type == "text"))
