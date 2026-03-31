from __future__ import annotations

from pydantic import BaseModel, Field


class HealthBasicResponse(BaseModel):
    """Overall process health: version and uptime since application start."""

    status: str = Field(examples=["ok"])
    version: str = Field(examples=["0.2.0"])
    uptime_seconds: float = Field(ge=0, examples=[42.5])

    model_config = {
        "json_schema_extra": {
            "examples": [{"status": "ok", "version": "0.2.0", "uptime_seconds": 12.3}],
        }
    }


class HealthReadyResponse(BaseModel):
    """Readiness: database connectivity."""

    status: str = Field(examples=["ready"])
    database: str = Field(description="Database probe result", examples=["connected"])

    model_config = {
        "json_schema_extra": {
            "examples": [{"status": "ready", "database": "connected"}],
        }
    }


class HealthLiveResponse(BaseModel):
    """Liveness: process is running (no dependency checks)."""

    status: str = Field(examples=["alive"])

    model_config = {
        "json_schema_extra": {
            "examples": [{"status": "alive"}],
        }
    }
