from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from dkb_runtime.models import (
    CanonicalDirective,
    LLMUsageLog,
    RawDirective,
    RawToCanonicalMap,
    ScoreCache,
    Source,
    SourceSnapshot,
)
from dkb_runtime.services.cost_tracker import get_usage_summary, log_usage
from dkb_runtime.services.score_cache import (
    get_cache_stats,
    get_cached_score,
    invalidate_cache,
    reset_cache_stats,
    score_cache_entry_counts,
    set_cached_score,
)


def _canon(db) -> CanonicalDirective:
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
        raw_name="T",
        entry_path="t.md",
        summary_raw="s",
        body_raw="b",
    )
    db.add(raw)
    db.commit()
    db.refresh(raw)
    canon = CanonicalDirective(preferred_name=f"cache-test-{uuid4().hex[:8]}", normalized_summary="s")
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
    db.refresh(canon)
    return canon


def test_score_cache_miss_hit_and_stats(db, dimension_model):
    reset_cache_stats()
    canon = _canon(db)
    fid = "fusion-v1"
    assert get_cached_score(db, canon.directive_id, dimension_model.dimension_model_id, "openai", fid) is None
    st = get_cache_stats()
    assert st["misses"] == 1 and st["hits"] == 0

    payload = {"dims": {"a": 0.5}}
    set_cached_score(db, canon.directive_id, dimension_model.dimension_model_id, "openai", fid, payload)
    db.commit()

    got = get_cached_score(db, canon.directive_id, dimension_model.dimension_model_id, "openai", fid)
    assert got == payload
    st = get_cache_stats()
    assert st["hits"] == 1

    counts = score_cache_entry_counts(db)
    assert counts["entries_total"] == 1
    assert counts["entries_active"] == 1


def test_score_cache_expired_not_returned(db, dimension_model):
    reset_cache_stats()
    canon = _canon(db)
    fid = "f2"
    set_cached_score(db, canon.directive_id, dimension_model.dimension_model_id, "mock", fid, {"x": 1}, ttl_hours=168)
    db.commit()
    row = db.scalars(select(ScoreCache)).first()
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(hours=1)
    db.commit()

    assert get_cached_score(db, canon.directive_id, dimension_model.dimension_model_id, "mock", fid) is None


def test_invalidate_cache_by_directive_and_all(db, dimension_model):
    c1 = _canon(db)
    c2 = _canon(db)
    set_cached_score(db, c1.directive_id, dimension_model.dimension_model_id, "openai", "k", {"a": 1})
    set_cached_score(db, c2.directive_id, dimension_model.dimension_model_id, "openai", "k", {"b": 2})
    db.commit()

    n = invalidate_cache(db, directive_id=c1.directive_id)
    db.commit()
    assert n >= 1
    remaining = db.scalars(select(ScoreCache)).all()
    assert len(remaining) == 1

    n2 = invalidate_cache(db, directive_id=None)
    db.commit()
    assert n2 >= 1
    assert db.scalars(select(ScoreCache)).all() == []


def test_cost_tracker_log_and_summary(db):
    log_usage(db, "openai", "gpt-4", 100, 50, 0.01)
    log_usage(db, "openai", "gpt-4", 200, 0, 0.02)
    log_usage(db, "anthropic", "claude-3", 10, 10, 0.005)
    db.commit()

    s = get_usage_summary(db, days=30)
    assert s["days"] == 30
    assert abs(s["total_cost_usd"] - 0.035) < 1e-9
    assert s["by_provider"]["openai"] == 0.03
    assert s["by_provider"]["anthropic"] == 0.005
    assert abs(s["by_model"]["gpt-4"] - 0.03) < 1e-9
    assert s["by_model"]["claude-3"] == 0.005


def test_cost_summary_respects_window(db):
    old = LLMUsageLog(
        request_id="old",
        provider="openai",
        model="x",
        input_tokens=1,
        output_tokens=1,
        cost_usd=1.0,
    )
    db.add(old)
    db.commit()
    old_row = db.scalars(select(LLMUsageLog)).first()
    assert old_row is not None
    old_row.created_at = datetime.now(UTC) - timedelta(days=60)
    db.commit()

    log_usage(db, "openai", "y", 1, 1, 0.1)
    db.commit()

    s = get_usage_summary(db, days=30)
    assert s["total_cost_usd"] == 0.1
