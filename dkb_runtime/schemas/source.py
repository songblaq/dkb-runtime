from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from dkb_runtime.schemas.common import ORMModel


class SourceCreate(BaseModel):
    source_kind: str
    origin_uri: str
    owner_name: str | None = None
    canonical_source_name: str | None = None
    provenance_hint: str | None = None
    metadata: dict = Field(default_factory=dict)


class SourceRead(ORMModel):
    source_id: UUID
    source_kind: str
    origin_uri: str
    owner_name: str | None = None
    canonical_source_name: str | None = None
    provenance_hint: str | None = None
    is_active: bool
    first_seen_at: datetime
    last_seen_at: datetime


class SnapshotCreate(BaseModel):
    revision_ref: str | None = None
    revision_type: str = "none"
    checksum: str | None = None
    license_text: str | None = None
    raw_blob_uri: str | None = None
    capture_status: str = "captured"
    snapshot_meta: dict = Field(default_factory=dict)


class SnapshotRead(ORMModel):
    snapshot_id: UUID
    source_id: UUID
    captured_at: datetime
    revision_ref: str | None = None
    revision_type: str
    checksum: str | None = None
    raw_blob_uri: str | None = None
    capture_status: str
    snapshot_meta: dict


class RawDirectiveCreate(BaseModel):
    raw_name: str
    entry_path: str | None = None
    declared_type: str | None = None
    content_format: str = "markdown"
    language_code: str = "en"
    summary_raw: str | None = None
    body_raw: str | None = None
    metadata: dict = Field(default_factory=dict)


class RawDirectiveRead(ORMModel):
    raw_directive_id: UUID
    snapshot_id: UUID
    raw_name: str
    entry_path: str | None = None
    declared_type: str | None = None
    content_format: str
    language_code: str | None = None
    summary_raw: str | None = None
    body_raw: str | None = None
