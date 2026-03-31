from __future__ import annotations

from uuid import uuid4

from dkb_runtime.models import (
    CanonicalDirective,
    RawDirective,
    RawToCanonicalMap,
    Source,
    SourceSnapshot,
)
from dkb_runtime.services.scoring import score_directive
from dkb_runtime.services.verdict import evaluate_directive


def _setup_directive(db, *, license_text: str | None, body: str = "MIT licensed project text"):
    src = Source(source_kind="local_folder", origin_uri=str(uuid4()))
    db.add(src)
    db.commit()
    db.refresh(src)
    snap = SourceSnapshot(
        source_id=src.source_id,
        license_text=license_text,
        raw_blob_uri="/tmp",
        capture_status="captured",
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    raw = RawDirective(
        snapshot_id=snap.snapshot_id,
        raw_name="V",
        body_raw=body,
    )
    db.add(raw)
    db.commit()
    db.refresh(raw)
    canon = CanonicalDirective(preferred_name="V", normalized_summary="s")
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


def test_verdict_no_license_triggers_caution_and_excluded(db, dimension_model):
    canon = _setup_directive(db, license_text=None, body="no license here")
    score_directive(db, canon.directive_id, dimension_model.dimension_model_id)
    db.commit()
    r = evaluate_directive(db, canon.directive_id)
    db.commit()
    assert r.legal_state == "no_license"
    assert r.trust_state == "caution"
    assert r.recommendation_state == "excluded"


def test_verdict_archived_lifecycle_deprecated(db, dimension_model):
    canon = _setup_directive(db, license_text="MIT License\nCopyright", body="x")
    canon.status = "archived"
    db.add(canon)
    db.commit()
    score_directive(db, canon.directive_id, dimension_model.dimension_model_id)
    db.commit()
    r = evaluate_directive(db, canon.directive_id)
    db.commit()
    assert r.lifecycle_state == "archived"
    assert r.recommendation_state == "deprecated"


def test_verdict_default_has_reviewing_trust_when_scores_exist(db, dimension_model):
    # License text must be long enough for clear legal_state (>20 chars) so
    # no_license_default_caution does not override trust_state to caution.
    canon = _setup_directive(
        db,
        license_text="MIT License\nCopyright (c) 2024 Example Corp",
        body="content",
    )
    score_directive(db, canon.directive_id, dimension_model.dimension_model_id)
    db.commit()
    r = evaluate_directive(db, canon.directive_id)
    db.commit()
    assert r.trust_state == "reviewing"
    assert r.verdict_reason
