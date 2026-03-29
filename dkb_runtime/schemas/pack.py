from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from dkb_runtime.schemas.common import ORMModel


class PackCreate(BaseModel):
    pack_key: str
    pack_name: str
    pack_goal: str
    pack_type: str = "custom"
    selection_policy: dict = Field(default_factory=dict)


class PackRead(ORMModel):
    pack_id: UUID
    pack_key: str
    pack_name: str
    pack_goal: str
    pack_type: str
    selection_policy: dict
    status: str
    created_at: datetime
