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


class PackBuildResponse(BaseModel):
    pack_id: str
    pack_name: str
    item_count: int
    status: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "pack_id": "00000000-0000-0000-0000-000000000001",
                    "pack_name": "My pack",
                    "item_count": 12,
                    "status": "built",
                }
            ],
        }
    }


class PackExportResponse(BaseModel):
    format: str
    output_path: str
    file_count: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "format": "claude-code",
                    "output_path": "/tmp/exports/pack/uuid",
                    "file_count": 5,
                }
            ],
        }
    }
