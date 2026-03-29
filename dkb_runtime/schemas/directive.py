from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from dkb_runtime.schemas.common import ORMModel


class CanonicalDirectiveCreate(BaseModel):
    preferred_name: str
    normalized_summary: str | None = None
    primary_human_label: str | None = None
    scope: str = "global"
    status: str = "active"
    canonical_meta: dict = Field(default_factory=dict)


class CanonicalDirectiveRead(ORMModel):
    directive_id: UUID
    preferred_name: str
    normalized_summary: str | None = None
    primary_human_label: str | None = None
    scope: str
    status: str
    canonical_meta: dict


class VectorSearchRequest(BaseModel):
    embedding: list[float]
    limit: int = 10
    embedding_model: str | None = None


class VectorSearchItem(BaseModel):
    directive_id: UUID
    preferred_name: str
    normalized_summary: str | None = None
    embedding_model: str
    distance: float


class FTSSearchItem(BaseModel):
    id: UUID
    name: str
    summary: str | None = None
    rank: float
