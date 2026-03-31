from __future__ import annotations

import json

from dkb_runtime.core.paths import repo_root
from dkb_runtime.models import CanonicalDirective, DimensionScore
from dkb_runtime.services.cognitive_ops import (
    cluster_directives,
    compare_directives,
    explain_profile,
)


def _dimension_config() -> dict:
    path = repo_root() / "config" / "dimension_model_v0_1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _add_full_scores(
    db,
    directive_id,
    dimension_model_id,
    *,
    score_value: float,
) -> None:
    cfg = _dimension_config()
    for g in cfg["groups"]:
        group = g["name"]
        for key in g["dimensions"]:
            db.add(
                DimensionScore(
                    directive_id=directive_id,
                    dimension_model_id=dimension_model_id,
                    dimension_group=group,
                    dimension_key=key,
                    score=score_value,
                    confidence=0.9,
                )
            )
    db.commit()


def test_compare_directives_score_diff(db, dimension_model):
    a = CanonicalDirective(preferred_name="A", normalized_summary="a")
    b = CanonicalDirective(preferred_name="B", normalized_summary="b")
    db.add_all([a, b])
    db.commit()
    db.refresh(a)
    db.refresh(b)
    _add_full_scores(db, a.directive_id, dimension_model.dimension_model_id, score_value=0.1)
    _add_full_scores(db, b.directive_id, dimension_model.dimension_model_id, score_value=0.4)

    out = compare_directives(db, a.directive_id, b.directive_id)
    assert out["embedding_cosine_distance"] is None
    assert len(out["dimensions"]) == 34
    skill = next(d for d in out["dimensions"] if d["dimension_key"] == "skillness")
    assert skill["score_a"] == 0.1
    assert skill["score_b"] == 0.4
    assert skill["diff"] == 0.3


def test_cluster_directives_groups_by_score_profile(db, dimension_model):
    """Synthetic score vectors: two low, one high — expect two clusters for k=2."""
    lows = []
    highs = []
    for i in range(2):
        d = CanonicalDirective(preferred_name=f"low-{i}", normalized_summary="x")
        db.add(d)
        lows.append(d)
    d_hi = CanonicalDirective(preferred_name="high-0", normalized_summary="y")
    db.add(d_hi)
    highs.append(d_hi)
    db.commit()
    for d in lows:
        db.refresh(d)
        _add_full_scores(db, d.directive_id, dimension_model.dimension_model_id, score_value=0.05)
    db.refresh(d_hi)
    _add_full_scores(db, d_hi.directive_id, dimension_model.dimension_model_id, score_value=0.95)

    clusters = cluster_directives(db, k=2)
    assert len(clusters) == 2
    total = sum(c["member_count"] for c in clusters)
    assert total == 3
    by_count = sorted(c["member_count"] for c in clusters)
    assert by_count == [1, 2]


def test_explain_profile_output_format():
    text = explain_profile({"skillness": 0.9, "agentness": 0.2, "planning": 0.8})
    assert text.startswith("Profile summary:")
    assert "mean" in text
    assert "\n" in text
    assert "form" in text
    assert "function" in text
