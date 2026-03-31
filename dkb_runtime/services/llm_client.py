"""LLM clients for hybrid directive scoring (lazy vendor imports)."""

from __future__ import annotations

import json
import os
import random
import re
from typing import Any, Protocol, runtime_checkable

from dkb_runtime.services import scoring_prompts


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _parse_scores_json(raw: str, dimensions: list[str]) -> dict[str, float]:
    """Extract JSON object from model output; fill missing keys with 0.5."""
    text = raw.strip()
    if not text:
        return {d: 0.5 for d in dimensions}
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```\s*$", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError:
        return {d: 0.5 for d in dimensions}
    if not isinstance(data, dict):
        return {d: 0.5 for d in dimensions}
    out: dict[str, float] = {}
    for d in dimensions:
        v = data.get(d, 0.5)
        try:
            out[d] = _clamp01(float(v))
        except (TypeError, ValueError):
            out[d] = 0.5
    return out


@runtime_checkable
class LLMClient(Protocol):
    def score_directive(self, text: str, dimensions: list[str]) -> dict[str, float]:
        """Return scores in [0,1] for each dimension key."""
        ...


class MockLLMClient:
    """Deterministic-enough random scores for tests (no API keys)."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def score_directive(self, text: str, dimensions: list[str]) -> dict[str, float]:
        return {d: _clamp01(self._rng.random()) for d in dimensions}


class OpenAIClient:
    """OpenAI Chat Completions with JSON-shaped output (lazy ``openai`` import)."""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or os.environ.get("OPENAI_SCORING_MODEL", "gpt-4o-mini")

    def score_directive(self, text: str, dimensions: list[str]) -> dict[str, float]:
        from openai import OpenAI

        system_msg, user_msg = scoring_prompts.build_scoring_messages_for_dimensions(text, dimensions)
        client = OpenAI()
        resp = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = (resp.choices[0].message.content or "").strip()
        return _parse_scores_json(content, dimensions)


class AnthropicClient:
    """Anthropic Messages API (lazy ``anthropic`` import)."""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or os.environ.get("ANTHROPIC_SCORING_MODEL", "claude-3-5-haiku-20241022")

    def score_directive(self, text: str, dimensions: list[str]) -> dict[str, float]:
        from anthropic import Anthropic

        system_msg, user_msg = scoring_prompts.build_scoring_messages_for_dimensions(text, dimensions)
        client = Anthropic()
        msg = client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system_msg,
            messages=[{"role": "user", "content": user_msg}],
        )
        parts: list[str] = []
        for block in msg.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        raw = "".join(parts)
        return _parse_scores_json(raw, dimensions)


def get_llm_client(provider: str | None = None) -> LLMClient:
    """Factory: ``provider`` or env ``DKB_LLM_PROVIDER`` = mock | openai | anthropic."""
    p = (provider or os.environ.get("DKB_LLM_PROVIDER", "mock")).lower().strip()
    if p == "mock":
        return MockLLMClient()
    if p == "openai":
        return OpenAIClient()
    if p == "anthropic":
        return AnthropicClient()
    raise ValueError(f"Unknown LLM provider: {p!r}; expected mock, openai, or anthropic")
