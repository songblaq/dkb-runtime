"""Collector service — acquires source snapshots."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID
from sqlalchemy import func
from sqlalchemy.orm import Session

from dkb_runtime.core.paths import repo_root
from dkb_runtime.models import Source, SourceSnapshot
from dkb_runtime.services.audit import log_audit

STORAGE_ROOT = repo_root() / "storage" / "snapshots"


@dataclass
class SnapshotResult:
    snapshot_id: UUID
    revision_ref: str
    capture_status: str
    raw_blob_uri: str


def collect_source(db: Session, source_id: UUID) -> SnapshotResult:
    source = db.get(Source, source_id)
    if not source:
        raise ValueError(f"Source not found: {source_id}")

    snapshot_id = uuid.uuid4()
    storage_path = STORAGE_ROOT / str(source_id) / str(snapshot_id)
    storage_path.mkdir(parents=True, exist_ok=True)

    revision_ref = ""
    capture_status = "captured"
    license_text = None

    if source.source_kind == "git_repo":
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", source.origin_uri, str(storage_path)],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            result = subprocess.run(
                ["git", "-C", str(storage_path), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
            revision_ref = result.stdout.strip()
        except subprocess.CalledProcessError:
            capture_status = "failed"
        except subprocess.TimeoutExpired:
            capture_status = "failed"
    elif source.source_kind == "local_folder":
        src = Path(source.origin_uri)
        if src.exists():
            shutil.copytree(src, storage_path, dirs_exist_ok=True)
            revision_ref = "local"
        else:
            capture_status = "failed"
    else:
        capture_status = "partial"

    if capture_status != "failed":
        for name in ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"]:
            license_path = storage_path / name
            if license_path.exists():
                license_text = license_path.read_text(errors="replace")[:10000]
                break

    snapshot = SourceSnapshot(
        snapshot_id=snapshot_id,
        source_id=source_id,
        revision_ref=revision_ref,
        revision_type="commit" if source.source_kind == "git_repo" else "none",
        checksum=revision_ref,
        license_text=license_text,
        raw_blob_uri=str(storage_path),
        capture_status=capture_status,
    )
    db.add(snapshot)

    source.last_seen_at = func.now()

    log_audit(
        db,
        "source",
        source_id,
        "collected",
        {
            "snapshot_id": str(snapshot_id),
            "capture_status": capture_status,
            "revision_ref": revision_ref,
        },
    )

    db.commit()

    return SnapshotResult(
        snapshot_id=snapshot_id,
        revision_ref=revision_ref,
        capture_status=capture_status,
        raw_blob_uri=str(storage_path),
    )
