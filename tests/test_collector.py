from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from dkb_runtime.models import Source, SourceSnapshot
from dkb_runtime.services.collector import SnapshotResult, collect_source


def test_collect_local_folder(db, tmp_path, fixtures_dir):
    dest = tmp_path / "copy"
    shutil.copytree(fixtures_dir / "sample_repo", dest)
    src = Source(
        source_kind="local_folder",
        origin_uri=str(dest),
    )
    db.add(src)
    db.commit()
    db.refresh(src)

    result = collect_source(db, src.source_id)
    assert isinstance(result, SnapshotResult)
    assert result.capture_status == "captured"
    assert result.revision_ref == "local"
    snap = db.get(SourceSnapshot, result.snapshot_id)
    assert snap is not None
    assert snap.license_text
    assert "MIT" in snap.license_text


def test_collect_source_not_found(db):
    with pytest.raises(ValueError, match="not found"):
        collect_source(db, uuid4())


def test_collect_git_failure(db):
    src = Source(
        source_kind="git_repo",
        origin_uri="https://example.invalid/repo-does-not-exist-xyz",
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    result = collect_source(db, src.source_id)
    assert result.capture_status == "failed"


def test_collect_git_shallow_clone(db, tmp_path):
    repo = tmp_path / "mini"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("# Mini\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    uri = repo.resolve().as_uri()
    src = Source(source_kind="git_repo", origin_uri=uri)
    db.add(src)
    db.commit()
    db.refresh(src)
    result = collect_source(db, src.source_id)
    assert result.capture_status == "captured"
    assert len(result.revision_ref) >= 7
    p = Path(result.raw_blob_uri)
    assert (p / "README.md").exists()
