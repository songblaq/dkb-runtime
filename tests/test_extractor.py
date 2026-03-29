from __future__ import annotations

import shutil

import pytest
from sqlalchemy import select

from dkb_runtime.models import RawDirective, Source, SourceSnapshot
from dkb_runtime.services.extractor import extract_directives


def test_extract_missing_snapshot(db):
    with pytest.raises(ValueError, match="not found"):
        extract_directives(db, __import__("uuid").uuid4())


def test_extract_from_sample_repo(db, tmp_path, fixtures_dir):
    tree = tmp_path / "tree"
    shutil.copytree(fixtures_dir / "sample_repo", tree)
    (tree / "nested").mkdir(exist_ok=True)
    (tree / "nested" / "README.md").write_text("# Nested Readme\n\nParagraph.\n", encoding="utf-8")
    src = Source(source_kind="local_folder", origin_uri=str(tmp_path))
    db.add(src)
    db.commit()
    db.refresh(src)
    snap = SourceSnapshot(
        source_id=src.source_id,
        raw_blob_uri=str(tree),
        capture_status="captured",
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)

    results = extract_directives(db, snap.snapshot_id)
    assert len(results) >= 1
    paths = {r.declared_type for r in results}
    assert "readme" in paths


def test_extract_skill_and_agent_priority(db, tmp_path, fixtures_dir):
    tree = tmp_path / "mixed"
    tree.mkdir()
    shutil.copytree(fixtures_dir / "sample_skill", tree / "a")
    shutil.copytree(fixtures_dir / "sample_agent", tree / "b")

    src = Source(source_kind="local_folder", origin_uri=str(tmp_path))
    db.add(src)
    db.commit()
    db.refresh(src)
    snap = SourceSnapshot(
        source_id=src.source_id,
        raw_blob_uri=str(tree),
        capture_status="captured",
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)

    results = extract_directives(db, snap.snapshot_id)
    types = {r.declared_type: r for r in results}
    assert "skill" in types
    assert "agent" in types
    skill = types["skill"]
    rds = db.scalars(select(RawDirective).where(RawDirective.raw_directive_id == skill.raw_directive_id)).one()
    assert rds.content_format == "markdown"
    assert skill.evidence_count >= 1
