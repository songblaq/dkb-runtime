from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from dkb_runtime.models import (
    CanonicalDirective,
    DirectiveRelation,
    RawDirective,
    RawToCanonicalMap,
    Source,
    SourceSnapshot,
)
from dkb_runtime.services.canonicalizer import CanonicalResult, _normalize_name, canonicalize


def test_normalize_name_strips_prefixes_and_separators():
    assert _normalize_name("Oh-My-Tool-Name") == "tool_name"
    assert _normalize_name("awesome-foo") == "foo"
    assert _normalize_name("Agent Planner Bot") == "agent_planner_bot"


def test_canonicalize_creates_maps_and_merges_duplicates(db):
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

    r1 = RawDirective(
        snapshot_id=snap.snapshot_id,
        raw_name="My Tool",
        summary_raw="short",
        body_raw="body",
    )
    r2 = RawDirective(
        snapshot_id=snap.snapshot_id,
        raw_name="oh-my-my_tool",
        summary_raw="longer summary text here",
        body_raw="body",
    )
    db.add_all([r1, r2])
    db.commit()
    db.refresh(r1)
    db.refresh(r2)

    results = canonicalize(db, [r1.raw_directive_id, r2.raw_directive_id])
    db.commit()
    assert len(results) == 1
    assert isinstance(results[0], CanonicalResult)
    assert results[0].mapped_raw_count == 2

    maps = db.scalars(select(RawToCanonicalMap)).all()
    assert len(maps) == 2


def test_canonicalizer_variant_relation(db):
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

    r1 = RawDirective(snapshot_id=snap.snapshot_id, raw_name="foo", body_raw="x")
    r2 = RawDirective(snapshot_id=snap.snapshot_id, raw_name="foobar", body_raw="y")
    db.add_all([r1, r2])
    db.commit()
    db.refresh(r1)
    db.refresh(r2)

    canonicalize(db, [r1.raw_directive_id, r2.raw_directive_id])
    db.commit()

    rels = db.scalars(select(DirectiveRelation).where(DirectiveRelation.relation_type == "variant_of")).all()
    assert len(rels) >= 1


def test_canonicalize_reuses_existing_canonical(db):
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

    existing = CanonicalDirective(preferred_name="existingtool", normalized_summary="s")
    db.add(existing)
    db.commit()
    db.refresh(existing)

    r = RawDirective(snapshot_id=snap.snapshot_id, raw_name="ExistingTool", body_raw="b")
    db.add(r)
    db.commit()
    db.refresh(r)

    canonicalize(db, [r.raw_directive_id])
    db.commit()
    maps = db.scalars(select(RawToCanonicalMap)).all()
    assert len(maps) == 1
    assert maps[0].directive_id == existing.directive_id
