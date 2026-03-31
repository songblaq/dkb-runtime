"""Cognitive operators: compare directives, cluster score profiles, recommend via embeddings, explain profiles."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from uuid import UUID

import numpy as np
from sklearn.cluster import KMeans
from sqlalchemy import select
from sqlalchemy.orm import Session

from dkb_runtime.core.paths import repo_root
from dkb_runtime.models import (
    CanonicalDirective,
    DimensionModel,
    DimensionScore,
    DirectiveEmbedding,
)


def _ordered_dimension_keys_from_config(config: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for group in config.get("groups", []):
        gname = str(group.get("name", ""))
        for key in group.get("dimensions", []):
            out.append((gname, str(key)))
    return out


def _active_dimension_model(db: Session) -> DimensionModel | None:
    return db.scalars(select(DimensionModel).where(DimensionModel.is_active.is_(True))).first()


def get_directive_dimension_scores(db: Session, directive_id: UUID, dimension_model_id: UUID) -> dict[str, float]:
    rows = db.scalars(
        select(DimensionScore).where(
            DimensionScore.directive_id == directive_id,
            DimensionScore.dimension_model_id == dimension_model_id,
        )
    ).all()
    return {r.dimension_key: float(r.score) for r in rows}


def _latest_embedding_row(
    db: Session, directive_id: UUID, model_name: str | None = None
) -> DirectiveEmbedding | None:
    stmt = select(DirectiveEmbedding).where(DirectiveEmbedding.directive_id == directive_id)
    if model_name is not None:
        stmt = stmt.where(DirectiveEmbedding.model_name == model_name)
    stmt = stmt.order_by(DirectiveEmbedding.created_at.desc()).limit(1)
    return db.scalars(stmt).first()


def _embedding_vec(row: DirectiveEmbedding | None) -> list[float] | None:
    if row is None or row.embedding is None:
        return None
    emb = row.embedding
    if hasattr(emb, "tolist"):
        return [float(x) for x in emb.tolist()]
    return [float(x) for x in emb]


def _cosine_distance_vectors(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return float("nan")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 1.0
    return 1.0 - dot / (na * nb)


def compare_directives(db: Session, id1: UUID, id2: UUID) -> dict:
    """Compare two directives: per-dimension score diff and embedding cosine distance (if both embedded)."""
    if db.get(CanonicalDirective, id1) is None:
        raise ValueError(f"Directive not found: {id1}")
    if db.get(CanonicalDirective, id2) is None:
        raise ValueError(f"Directive not found: {id2}")

    dim_model = _active_dimension_model(db)
    if dim_model is None:
        raise ValueError("No active dimension model")

    keys = _ordered_dimension_keys_from_config(dim_model.config)
    m1 = get_directive_dimension_scores(db, id1, dim_model.dimension_model_id)
    m2 = get_directive_dimension_scores(db, id2, dim_model.dimension_model_id)

    dimensions: list[dict] = []
    for group, key in keys:
        s1 = m1.get(key)
        s2 = m2.get(key)
        diff: float | None = (s2 - s1) if s1 is not None and s2 is not None else None
        dimensions.append(
            {
                "dimension_group": group,
                "dimension_key": key,
                "score_a": s1,
                "score_b": s2,
                "diff": diff,
            }
        )

    e1 = _latest_embedding_row(db, id1)
    e2 = _latest_embedding_row(db, id2)
    v1 = _embedding_vec(e1)
    v2 = _embedding_vec(e2)
    embedding_cosine_distance: float | None
    if v1 is not None and v2 is not None and e1 is not None and e2 is not None:
        embedding_cosine_distance = (
            None if e1.model_name != e2.model_name else float(_cosine_distance_vectors(v1, v2))
        )
    else:
        embedding_cosine_distance = None

    return {
        "directive_id_a": str(id1),
        "directive_id_b": str(id2),
        "dimension_model_id": str(dim_model.dimension_model_id),
        "dimensions": dimensions,
        "embedding_cosine_distance": embedding_cosine_distance,
        "embedding_model": e1.model_name if e1 is not None else None,
    }


def cluster_directives(db: Session, k: int = 5) -> list[dict]:
    """K-means on 34-dim DKB score vectors (one row per directive with any scores for the active model)."""
    dim_model = _active_dimension_model(db)
    if dim_model is None:
        raise ValueError("No active dimension model")

    keys = _ordered_dimension_keys_from_config(dim_model.config)
    if not keys:
        return []

    stmt = select(DimensionScore.directive_id).where(
        DimensionScore.dimension_model_id == dim_model.dimension_model_id
    )
    directive_ids = list({row[0] for row in db.execute(stmt).all()})
    if not directive_ids:
        return []

    vectors: list[list[float]] = []
    ids_out: list[UUID] = []
    for did in directive_ids:
        smap = get_directive_dimension_scores(db, did, dim_model.dimension_model_id)
        vec = [float(smap.get(key, 0.0)) for _, key in keys]
        vectors.append(vec)
        ids_out.append(did)

    X = np.asarray(vectors, dtype=np.float64)
    n = X.shape[0]
    n_clusters = max(1, min(int(k), n))
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(X)

    buckets: dict[int, list[UUID]] = defaultdict(list)
    for did, label in zip(ids_out, labels, strict=True):
        buckets[int(label)].append(did)

    return [
        {
            "cluster_id": cid,
            "directive_ids": [str(u) for u in sorted(buckets[cid], key=lambda u: str(u))],
            "member_count": len(buckets[cid]),
        }
        for cid in sorted(buckets.keys())
    ]


def recommend_similar(db: Session, directive_id: UUID, n: int = 5, model_name: str | None = None) -> list[dict]:
    """Recommend similar directives using stored embedding cosine distance (lower is closer)."""
    from dkb_runtime.services.embedding import find_similar_to_directive

    if db.get(CanonicalDirective, directive_id) is None:
        raise ValueError(f"Directive not found: {directive_id}")
    pairs = find_similar_to_directive(db, directive_id, limit=n, model_name=model_name)
    return [
        {"directive_id": str(did), "cosine_distance": float(dist)}
        for did, dist in pairs
    ]


def explain_profile(directive_scores: dict) -> str:
    """Template-based natural language summary of a DKB dimension profile (no LLM)."""
    cfg_path = repo_root() / "config" / "dimension_model_v0_1.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    scores: dict[str, float] = {}
    for raw_k, raw_v in directive_scores.items():
        try:
            scores[str(raw_k)] = float(raw_v)
        except (TypeError, ValueError):
            continue

    if not scores:
        return "No scored dimensions provided; cannot summarize."

    lines: list[str] = []
    all_vals = list(scores.values())
    overall = sum(all_vals) / len(all_vals)
    hi = sum(1 for x in all_vals if x >= 0.66)
    lo = sum(1 for x in all_vals if x <= 0.33)
    lines.append(
        f"Profile summary: {len(scores)} dimension(s) scored; mean {overall:.2f} on a 0–1 scale. "
        f"{hi} high (≥0.66), {lo} low (≤0.33)."
    )

    for group in cfg.get("groups", []):
        gname = str(group.get("name", ""))
        dims = [str(d) for d in group.get("dimensions", [])]
        vals = [(d, scores[d]) for d in dims if d in scores]
        if len(vals) < 2:
            if len(vals) == 1:
                d0, v0 = vals[0]
                lines.append(f"{gname}: only {d0} is scored ({v0:.2f}).")
            continue
        avg = sum(v for _, v in vals) / len(vals)
        top = sorted(vals, key=lambda x: -x[1])[:3]
        low = sorted(vals, key=lambda x: x[1])[:3]
        top_s = ", ".join(f"{k} ({v:.2f})" for k, v in top)
        low_s = ", ".join(f"{k} ({v:.2f})" for k, v in low)
        lines.append(
            f"{gname} (mean {avg:.2f}): relatively strong on {top_s}; relatively weak on {low_s}."
        )

    return "\n".join(lines)
