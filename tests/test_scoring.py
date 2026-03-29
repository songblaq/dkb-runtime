from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from dkb_runtime.models import (
    CanonicalDirective,
    DimensionScore,
    RawDirective,
    RawToCanonicalMap,
    Source,
    SourceSnapshot,
)
from dkb_runtime.services.scoring import score_directive


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
        raw_name="Code Helper",
        declared_type="agent",
        entry_path="agents/helper.md",
        summary_raw="Reviews and implements code.",
        body_raw=body,
    )
    db.add(raw)
    db.commit()
    db.refresh(raw)
    canon = CanonicalDirective(
        preferred_name="Code Helper",
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


def test_scoring_returns_34_dimensions_in_range(db, dimension_model):
    body = """
    # Agent
    This agent plans strategy, reviews pull requests, implements code,
    searches documentation, deploys to CI/CD, and orchestrates workflows.
    ```bash
    npm install
    ```
    """
    canon = _directive_with_body(db, body)
    results = score_directive(db, canon.directive_id, dimension_model.dimension_model_id)
    db.commit()
    assert len(results) == 34
    for r in results:
        assert 0 <= r.score <= 1
        assert 0 <= r.confidence <= 1
        assert r.explanation


def test_scoring_function_group_keywords(db, dimension_model):
    canon = _directive_with_body(db, "This tool reviews code and runs lint checks.")
    results = score_directive(db, canon.directive_id, dimension_model.dimension_model_id)
    db.commit()
    by_key = {r.dimension_key: r for r in results}
    assert by_key["review"].score > 0


def test_scoring_replaces_previous_scores(db, dimension_model):
    canon = _directive_with_body(db, "first")
    score_directive(db, canon.directive_id, dimension_model.dimension_model_id)
    db.commit()
    score_directive(db, canon.directive_id, dimension_model.dimension_model_id)
    db.commit()
    rows = db.scalars(
        select(DimensionScore).where(DimensionScore.directive_id == canon.directive_id)
    ).all()
    assert len(rows) == 34
