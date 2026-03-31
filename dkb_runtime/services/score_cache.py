from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from dkb_runtime.models.cache import ScoreCache

_cache_stats: dict[str, int] = {"hits": 0, "misses": 0}


def get_cache_stats() -> dict[str, Any]:
    """Return process-local hit/miss counters plus aggregate labels for CLI."""
    hits = _cache_stats["hits"]
    misses = _cache_stats["misses"]
    total = hits + misses
    hit_rate = (hits / total) if total else 0.0
    return {"hits": hits, "misses": misses, "hit_rate": hit_rate, "total_lookups": total}


def reset_cache_stats() -> None:
    """Reset process-local hit/miss counters (e.g. for tests)."""
    _cache_stats["hits"] = 0
    _cache_stats["misses"] = 0


def get_cached_score(
    db: Session,
    directive_id: UUID,
    dim_model_id: UUID,
    provider: str,
    fusion_config_id: str,
) -> dict | None:
    now = datetime.now(UTC)
    row = db.scalars(
        select(ScoreCache).where(
            ScoreCache.directive_id == directive_id,
            ScoreCache.dimension_model_id == dim_model_id,
            ScoreCache.provider == provider,
            ScoreCache.fusion_config_id == fusion_config_id,
            ScoreCache.expires_at > now,
        )
    ).first()
    if row is not None:
        _cache_stats["hits"] += 1
        return dict(row.scores_json) if isinstance(row.scores_json, dict) else row.scores_json
    _cache_stats["misses"] += 1
    return None


def set_cached_score(
    db: Session,
    directive_id: UUID,
    dim_model_id: UUID,
    provider: str,
    fusion_config_id: str,
    scores: dict,
    ttl_hours: int = 168,
) -> None:
    expires_at = datetime.now(UTC) + timedelta(hours=ttl_hours)
    db.execute(
        delete(ScoreCache).where(
            ScoreCache.directive_id == directive_id,
            ScoreCache.dimension_model_id == dim_model_id,
            ScoreCache.provider == provider,
            ScoreCache.fusion_config_id == fusion_config_id,
        )
    )
    db.add(
        ScoreCache(
            directive_id=directive_id,
            dimension_model_id=dim_model_id,
            provider=provider,
            fusion_config_id=fusion_config_id,
            scores_json=scores,
            expires_at=expires_at,
        )
    )


def invalidate_cache(db: Session, directive_id: UUID | None = None) -> int:
    """Delete score cache rows; all rows if directive_id is None. Returns deleted row count."""
    if directive_id is None:
        res = db.execute(delete(ScoreCache))
    else:
        res = db.execute(delete(ScoreCache).where(ScoreCache.directive_id == directive_id))
    return res.rowcount or 0


def score_cache_entry_counts(db: Session) -> dict[str, int]:
    """Counts for CLI stats (DB-backed)."""
    now = datetime.now(UTC)
    total = db.scalar(select(func.count()).select_from(ScoreCache)) or 0
    active = (
        db.scalar(select(func.count()).select_from(ScoreCache).where(ScoreCache.expires_at > now)) or 0
    )
    return {"entries_total": int(total), "entries_active": int(active)}
