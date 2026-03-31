from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dkb_runtime.models.cache import LLMUsageLog


def log_usage(
    db: Session,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> LLMUsageLog:
    row = LLMUsageLog(
        request_id=str(uuid4()),
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )
    db.add(row)
    return row


def get_usage_summary(db: Session, days: int = 30) -> dict:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    rows = db.execute(
        select(
            LLMUsageLog.provider,
            LLMUsageLog.model,
            func.sum(LLMUsageLog.cost_usd).label("cost_sum"),
        )
        .where(LLMUsageLog.created_at >= cutoff)
        .group_by(LLMUsageLog.provider, LLMUsageLog.model)
    ).all()

    by_provider: dict[str, float] = {}
    by_model: dict[str, float] = {}
    total_cost = 0.0
    for provider, model, cost_sum in rows:
        c = float(cost_sum or 0.0)
        total_cost += c
        by_provider[provider] = by_provider.get(provider, 0.0) + c
        by_model[model] = by_model.get(model, 0.0) + c

    return {
        "days": days,
        "total_cost_usd": total_cost,
        "by_provider": dict(sorted(by_provider.items(), key=lambda x: x[0])),
        "by_model": dict(sorted(by_model.items(), key=lambda x: x[0])),
    }
