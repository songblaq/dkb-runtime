"""Embedding generation (OpenAI or mock) and pgvector similarity helpers."""

from __future__ import annotations

import os
import random
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from dkb_runtime.models import CanonicalDirective, DirectiveEmbedding

_DEFAULT_DIM = 1536


def _mock_embedding(text: str, model: str, dim: int = _DEFAULT_DIM) -> list[float]:
    """Deterministic pseudo-random unit-norm vector for tests and offline use."""
    seed = (hash(text) ^ hash(model)) & 0xFFFFFFFF
    rng = random.Random(seed)
    vec = [rng.gauss(0.0, 1.0) for _ in range(dim)]
    norm = sum(x * x for x in vec) ** 0.5
    if norm == 0:
        return [0.0] * dim
    return [x / norm for x in vec]


def generate_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Return a ``dim``-dimensional embedding using OpenAI when configured, else mock vectors."""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        try:
            from openai import OpenAI  # noqa: E402

            client = OpenAI()
            response = client.embeddings.create(input=text, model=model)
            return list(response.data[0].embedding)
        except ImportError:
            pass
        except Exception:
            pass
    return _mock_embedding(text, model)


def store_embedding(
    db: Session,
    directive_id: UUID,
    embedding: list[float],
    model_name: str,
    *,
    embedding_dim: int | None = None,
) -> DirectiveEmbedding:
    """Insert or replace embedding for ``(directive_id, model_name)`` (unique in schema)."""
    dim = embedding_dim if embedding_dim is not None else len(embedding)
    db.execute(
        delete(DirectiveEmbedding).where(
            DirectiveEmbedding.directive_id == directive_id,
            DirectiveEmbedding.model_name == model_name,
        )
    )
    row = DirectiveEmbedding(
        directive_id=directive_id,
        embedding=embedding,
        model_name=model_name,
        embedding_dim=dim,
    )
    db.add(row)
    db.flush()
    return row


def find_similar(
    db: Session,
    query_embedding: list[float],
    *,
    limit: int = 10,
    model_name: str | None = None,
) -> list[tuple[UUID, float]]:
    """Cosine distance to query (lower is more similar)."""
    stmt = (
        select(
            DirectiveEmbedding.directive_id,
            DirectiveEmbedding.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .order_by(text("distance ASC"))
        .limit(limit)
    )
    if model_name is not None:
        stmt = stmt.where(DirectiveEmbedding.model_name == model_name)
    rows = db.execute(stmt).all()
    return [(row.directive_id, float(row.distance)) for row in rows]


def find_similar_to_directive(
    db: Session,
    directive_id: UUID,
    *,
    limit: int = 10,
    model_name: str | None = None,
) -> list[tuple[UUID, float]]:
    """Similar directives using the latest stored embedding for ``directive_id``."""
    emb_stmt = select(DirectiveEmbedding).where(DirectiveEmbedding.directive_id == directive_id)
    if model_name is not None:
        emb_stmt = emb_stmt.where(DirectiveEmbedding.model_name == model_name)
    emb_stmt = emb_stmt.order_by(DirectiveEmbedding.created_at.desc()).limit(1)
    ref = db.scalars(emb_stmt).first()
    if ref is None:
        return []
    stmt = (
        select(
            DirectiveEmbedding.directive_id,
            DirectiveEmbedding.embedding.cosine_distance(ref.embedding).label("distance"),
        )
        .where(DirectiveEmbedding.directive_id != directive_id)
        .order_by(text("distance ASC"))
        .limit(limit)
    )
    if model_name is not None:
        stmt = stmt.where(DirectiveEmbedding.model_name == model_name)
    rows = db.execute(stmt).all()
    return [(row.directive_id, float(row.distance)) for row in rows]


def directive_text_for_embedding(db: Session, directive_id: UUID) -> str | None:
    """Concatenate fields used as embedding input for a canonical directive."""
    d = db.get(CanonicalDirective, directive_id)
    if not d:
        return None
    parts = [d.preferred_name or "", d.normalized_summary or "", d.primary_human_label or ""]
    return " ".join(p for p in parts if p).strip() or None
