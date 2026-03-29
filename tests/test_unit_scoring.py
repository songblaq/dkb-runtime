"""Pure unit tests for scoring and name-normalization helpers (no database)."""

from __future__ import annotations

import pytest

from dkb_runtime.services.canonicalizer import _normalize_name
from dkb_runtime.services.scoring import _clamp01, _score_keyword_presence


def test_score_keyword_presence_empty() -> None:
    score, conf, explanation = _score_keyword_presence("", ["a", "b"])
    assert score == 0.0
    assert "0/2" in explanation
    assert conf == pytest.approx(0.5)


def test_score_keyword_presence_matches_and_clamps() -> None:
    content = "Invoke this skill: capability and single task workflow."
    score, conf, explanation = _score_keyword_presence(
        content, ["skill", "capability", "single task", "invoke", "missing_kw"]
    )
    assert score == pytest.approx(1.0)
    assert "4/5" in explanation
    assert conf > 0.5


def test_score_keyword_presence_case_insensitive() -> None:
    score, _, explanation = _score_keyword_presence("AGENT and PLANNER", ["agent", "planner"])
    assert score > 0
    assert "agent" in explanation.lower()


def test_clamp01_bounds() -> None:
    assert _clamp01(-1) == 0.0
    assert _clamp01(2) == 1.0
    assert _clamp01(0.5) == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("skill-my-pack", "my_pack"),
        ("claude-code-helper", "helper"),
        ("oh-my-widget", "widget"),
        ("Foo Bar-Baz!", "foo_bar_baz"),
    ],
)
def test_normalize_name_additional_prefixes_and_chars(raw: str, expected: str) -> None:
    assert _normalize_name(raw) == expected


def test_normalize_name_strips_whitespace() -> None:
    assert _normalize_name("  MyName  ") == "myname"
