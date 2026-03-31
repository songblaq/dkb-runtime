from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from dkb_runtime.models import (
    CanonicalDirective,
    DimensionScore,
    RawDirective,
    RawToCanonicalMap,
    Source,
    SourceSnapshot,
)
from dkb_runtime.services.llm_client import MockLLMClient, get_llm_client
from dkb_runtime.services.scoring import hybrid_score_directive
from dkb_runtime.services.scoring_prompts import (
    GROUP_PROMPT_TEMPLATE,
    build_group_scoring_prompt,
    build_scoring_messages_for_dimensions,
    infer_group_for_dimensions,
)


def _directive_with_body(db, body: str) -> CanonicalDirective:
    src = Source(source_kind="local_folder", origin_uri=str(uuid4()))
    db.add(src)
    db.commit()
    db.refresh(src)
    snap = SourceSnapshot(
        source_id=src.source_id,
        raw_blob_uri="/tmp",
        capture_status="captured",
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    raw = RawDirective(
        snapshot_id=snap.snapshot_id,
        raw_name="LLM Test",
        declared_type="skill",
        entry_path=".claude/skills/test/SKILL.md",
        summary_raw="Test directive for hybrid scoring.",
        body_raw=body,
    )
    db.add(raw)
    db.commit()
    db.refresh(raw)
    canon = CanonicalDirective(
        preferred_name=f"LLM Test {uuid4().hex[:8]}",
        normalized_summary=raw.summary_raw,
    )
    db.add(canon)
    db.flush()
    db.add(
        RawToCanonicalMap(
            raw_directive_id=raw.raw_directive_id,
            directive_id=canon.directive_id,
            mapping_score=1.0,
            mapping_status="accepted",
        )
    )
    db.commit()
    return canon


def test_mock_llm_client_returns_clamped_scores_per_dimension() -> None:
    client = MockLLMClient(seed=42)
    dims = ["skillness", "agentness"]
    out = client.score_directive("hello", dims)
    assert set(out.keys()) == set(dims)
    for v in out.values():
        assert 0.0 <= v <= 1.0


def test_mock_llm_client_deterministic_with_seed() -> None:
    a = MockLLMClient(seed=7).score_directive("x", ["a", "b"])
    b = MockLLMClient(seed=7).score_directive("x", ["a", "b"])
    assert a == b


def test_hybrid_scoring_with_mock_fuses_and_persists(db, dimension_model) -> None:
    canon = _directive_with_body(db, "This skill reviews code and runs npm install.")
    mock = MockLLMClient(seed=123)
    fusion = {"rule_weight": 0.5, "llm_weight": 0.5, "fusion_config_id": "test-fusion"}
    results = hybrid_score_directive(
        db,
        canon.directive_id,
        dimension_model.dimension_model_id,
        fusion_config=fusion,
        llm_client=mock,
    )
    db.commit()
    assert len(results) == 34
    rows = db.scalars(
        select(DimensionScore).where(
            DimensionScore.directive_id == canon.directive_id,
            DimensionScore.dimension_model_id == dimension_model.dimension_model_id,
        )
    ).all()
    assert len(rows) == 34
    for row in rows:
        assert 0 <= row.score <= 1
        assert row.features.get("llm_scored") is True
        assert row.features.get("fusion_config_id") == "test-fusion"
        assert "rule_score" in row.features and "llm_score" in row.features
        expected = 0.5 * float(row.features["rule_score"]) + 0.5 * float(row.features["llm_score"])
        assert row.score == pytest.approx(expected, abs=1e-6)


def test_prompt_generation_all_six_groups() -> None:
    text = "Sample directive body for prompt tests."
    for group in ("form", "function", "execution", "governance", "adoption", "clarity"):
        assert group in GROUP_PROMPT_TEMPLATE
        sample = {
            "form": ["skillness"],
            "function": ["planning"],
            "execution": ["atomicity"],
            "governance": ["officialness"],
            "adoption": ["star_signal"],
            "clarity": ["naming_clarity"],
        }[group]
        prompt = build_group_scoring_prompt(group, text, sample)
        assert "JSON" in prompt
        assert text in prompt
        assert sample[0] in prompt


def test_build_scoring_messages_and_infer_group() -> None:
    dims = ["review", "coding"]
    assert infer_group_for_dimensions(dims) == "function"
    system, user = build_scoring_messages_for_dimensions("doc", dims)
    assert "JSON" in system
    assert "review" in user and "coding" in user


def test_infer_group_rejects_mixed() -> None:
    with pytest.raises(ValueError, match="multiple groups"):
        infer_group_for_dimensions(["skillness", "planning"])


def test_get_llm_client_mock_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DKB_LLM_PROVIDER", raising=False)
    c = get_llm_client()
    assert isinstance(c, MockLLMClient)


def test_get_llm_client_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DKB_LLM_PROVIDER", "mock")
    assert isinstance(get_llm_client(), MockLLMClient)


def test_get_llm_client_explicit_provider_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DKB_LLM_PROVIDER", "openai")
    assert isinstance(get_llm_client("mock"), MockLLMClient)


def test_example_json_snippet_in_prompt_matches_dimensions() -> None:
    dims = ["skillness", "agentness", "workflowness", "commandness", "pluginness"]
    p = build_group_scoring_prompt("form", "x", dims)
    compact = p.replace(" ", "")
    for d in dims:
        assert f'"{d}":0.0' in compact
