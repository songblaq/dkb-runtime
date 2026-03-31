"""Canonicalizer service — deduplicates and normalizes directives."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from dkb_runtime.models import (
    CanonicalDirective,
    DirectiveRelation,
    RawDirective,
    RawToCanonicalMap,
)
from dkb_runtime.models.embedding import DirectiveEmbedding
from dkb_runtime.services import embedding as embedding_svc
from dkb_runtime.services.audit import log_audit

DEFAULT_SIMILARITY_THRESHOLD = 0.85
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
_NAME_SUBSTRING_SIMILARITY = 0.88


@dataclass
class CanonicalResult:
    directive_id: UUID
    preferred_name: str
    mapped_raw_count: int


@dataclass(frozen=True)
class SimilarMatch:
    """A canonical directive that may duplicate the query (embedding or name-based)."""

    directive_id: UUID
    similarity: float
    match_kind: str  # "embedding" | "name"


def _normalize_name(raw_name: str) -> str:
    name = raw_name.lower().strip()
    for prefix in ["oh-my-", "awesome-", "claude-code-", "agent-", "skill-"]:
        if name.startswith(prefix):
            name = name[len(prefix) :]
    name = re.sub(r"[-\s]+", "_", name)
    name = re.sub(r"[^a-z0-9_]", "", name)
    return name


def _distance_to_cosine_similarity(distance: float) -> float:
    """pgvector cosine distance is ``1 - cosine_similarity`` for unit vectors."""
    return 1.0 - float(distance)


def _latest_embedding_vector(db: Session, directive_id: UUID, model_name: str | None) -> list[float] | None:
    stmt = select(DirectiveEmbedding).where(DirectiveEmbedding.directive_id == directive_id)
    if model_name is not None:
        stmt = stmt.where(DirectiveEmbedding.model_name == model_name)
    stmt = stmt.order_by(DirectiveEmbedding.created_at.desc()).limit(1)
    row = db.scalars(stmt).first()
    if row is None or row.embedding is None:
        return None
    emb = row.embedding
    if hasattr(emb, "tolist"):
        return [float(x) for x in emb.tolist()]
    return [float(x) for x in emb]


def _name_similarity_score(query_norm: str, canon_norm: str) -> float | None:
    if query_norm == canon_norm:
        return 1.0
    if len(query_norm) < 3 or len(canon_norm) < 3:
        return None
    if query_norm in canon_norm or canon_norm in query_norm:
        return _NAME_SUBSTRING_SIMILARITY
    return None


def _name_fallback_matches(
    db: Session,
    query_norm: str,
    *,
    similarity_threshold: float,
    exclude_directive_id: UUID | None = None,
) -> list[SimilarMatch]:
    if not query_norm:
        return []
    canons = db.scalars(select(CanonicalDirective)).all()
    out: list[SimilarMatch] = []
    for c in canons:
        if exclude_directive_id is not None and c.directive_id == exclude_directive_id:
            continue
        cn = _normalize_name(c.preferred_name)
        score = _name_similarity_score(query_norm, cn)
        if score is not None and score >= similarity_threshold:
            out.append(SimilarMatch(directive_id=c.directive_id, similarity=score, match_kind="name"))
    out.sort(key=lambda m: m.similarity, reverse=True)
    return out


def _pick_best_raw(raws: list[RawDirective]) -> RawDirective:
    def key(r: RawDirective) -> tuple[int, int]:
        n_ev = len(r.evidence_items) if r.evidence_items else 0
        return (n_ev, len(r.summary_raw or ""))

    return max(raws, key=key)


def _relation_exists(
    db: Session,
    left_id: UUID,
    right_id: UUID,
    relation_type: str,
) -> bool:
    stmt = select(DirectiveRelation).where(
        DirectiveRelation.relation_type == relation_type,
        or_(
            and_(
                DirectiveRelation.left_directive_id == left_id,
                DirectiveRelation.right_directive_id == right_id,
            ),
            and_(
                DirectiveRelation.left_directive_id == right_id,
                DirectiveRelation.right_directive_id == left_id,
            ),
        ),
    )
    return db.scalars(stmt.limit(1)).first() is not None


@dataclass
class Canonicalizer:
    """Deduplicate raw directives using normalized names and optional embedding similarity."""

    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    embedding_search_limit: int = 10

    def find_similar(
        self,
        db: Session,
        *,
        directive_id: UUID | None = None,
        query_text: str | None = None,
        limit: int = 10,
        exclude_directive_id: UUID | None = None,
    ) -> list[SimilarMatch]:
        """Return potential duplicate canonical directives with cosine (or name) similarity scores.

        Uses embedding cosine similarity when a query vector can be built; otherwise falls back
        to normalized name / substring rules. ``exclude_directive_id`` drops that id from results
        (defaults to ``directive_id`` when only ``directive_id`` is provided).
        """
        if (directive_id is None) == (query_text is None):
            raise ValueError("Provide exactly one of directive_id or query_text")

        excl = exclude_directive_id if exclude_directive_id is not None else directive_id

        query_norm: str | None = None
        if query_text is not None:
            query_norm = _normalize_name(query_text)
        elif directive_id is not None:
            d = db.get(CanonicalDirective, directive_id)
            if d is None:
                raise ValueError(f"Directive not found: {directive_id}")
            query_norm = _normalize_name(d.preferred_name or "")

        vec: list[float] | None = None
        if directive_id is not None:
            vec = _latest_embedding_vector(db, directive_id, self.embedding_model)
            if vec is None:
                t = embedding_svc.directive_text_for_embedding(db, directive_id)
                if t:
                    vec = embedding_svc.generate_embedding(t, self.embedding_model)
        elif query_text is not None and query_text.strip():
            vec = embedding_svc.generate_embedding(query_text.strip(), self.embedding_model)

        matches: list[SimilarMatch] = []
        if vec is not None:
            pairs = embedding_svc.find_similar(
                db,
                vec,
                limit=max(limit * 4, self.embedding_search_limit),
                model_name=self.embedding_model,
            )
            for did, dist in pairs:
                if excl is not None and did == excl:
                    continue
                sim = _distance_to_cosine_similarity(dist)
                if sim >= self.similarity_threshold:
                    matches.append(SimilarMatch(directive_id=did, similarity=sim, match_kind="embedding"))

        if not matches and query_norm is not None:
            matches = _name_fallback_matches(
                db,
                query_norm,
                similarity_threshold=self.similarity_threshold,
                exclude_directive_id=excl,
            )

        by_id: dict[UUID, SimilarMatch] = {}
        for m in matches:
            prev = by_id.get(m.directive_id)
            if prev is None or m.similarity > prev.similarity:
                by_id[m.directive_id] = m
        ranked = sorted(by_id.values(), key=lambda x: x.similarity, reverse=True)
        return ranked[:limit]

    def canonicalize(self, db: Session, raw_directive_ids: list[UUID]) -> list[CanonicalResult]:
        if not raw_directive_ids:
            return []

        raws = db.scalars(
            select(RawDirective)
            .options(selectinload(RawDirective.evidence_items))
            .where(RawDirective.raw_directive_id.in_(raw_directive_ids))
        ).all()
        if len(raws) != len(set(raw_directive_ids)):
            raise ValueError("One or more raw_directive_ids were not found")

        existing_canons = db.scalars(select(CanonicalDirective)).all()
        norm_to_canon: dict[str, CanonicalDirective] = {}
        for c in existing_canons:
            n = _normalize_name(c.preferred_name)
            if n not in norm_to_canon:
                norm_to_canon[n] = c

        groups: dict[str, list[RawDirective]] = {}
        for r in raws:
            groups.setdefault(_normalize_name(r.raw_name), []).append(r)

        results: list[CanonicalResult] = []
        touched_directives: dict[UUID, list[RawDirective]] = {}

        for norm, group in groups.items():
            best = _pick_best_raw(group)
            existing = norm_to_canon.get(norm)
            vec_for_store: list[float] | None = None

            if existing is None:
                qtext = f"{best.raw_name}\n{best.summary_raw or ''}".strip()
                if qtext:
                    vec_for_store = embedding_svc.generate_embedding(qtext, self.embedding_model)
                    pairs = embedding_svc.find_similar(
                        db,
                        vec_for_store,
                        limit=self.embedding_search_limit,
                        model_name=self.embedding_model,
                    )
                    for did, dist in pairs:
                        sim = _distance_to_cosine_similarity(dist)
                        if sim < self.similarity_threshold:
                            continue
                        cand = db.get(CanonicalDirective, did)
                        if cand is not None:
                            existing = cand
                            norm_to_canon[norm] = existing
                            break

            if existing is None:
                canon = CanonicalDirective(
                    preferred_name=best.raw_name,
                    normalized_summary=best.summary_raw,
                    primary_human_label=best.raw_name,
                    scope="global",
                    status="active",
                    canonical_meta={"normalized_key": norm},
                )
                db.add(canon)
                db.flush()
                norm_to_canon[norm] = canon
                existing = canon
                if vec_for_store is None:
                    qtext = f"{best.raw_name}\n{best.summary_raw or ''}".strip()
                    if qtext:
                        vec_for_store = embedding_svc.generate_embedding(qtext, self.embedding_model)

            canon = existing

            if vec_for_store is not None:
                embedding_svc.store_embedding(db, canon.directive_id, vec_for_store, self.embedding_model)

            touched_directives.setdefault(canon.directive_id, []).extend(group)

            for r in group:
                db.add(
                    RawToCanonicalMap(
                        raw_directive_id=r.raw_directive_id,
                        directive_id=canon.directive_id,
                        mapping_score=1.0 if r.raw_directive_id == best.raw_directive_id else 0.85,
                        mapping_reason="primary" if len(group) == 1 else "dedup",
                        mapping_status="accepted",
                    )
                )

        uniq_canons = {c.directive_id: c for c in norm_to_canon.values()}.values()
        canon_list = list(uniq_canons)

        for i, a in enumerate(canon_list):
            for b in canon_list[i + 1 :]:
                na = _normalize_name(a.preferred_name)
                nb = _normalize_name(b.preferred_name)
                if na == nb:
                    continue
                if len(na) < 3 or len(nb) < 3:
                    continue
                if not (na in nb or nb in na):
                    continue
                left, right = (a, b) if len(na) <= len(nb) else (b, a)
                if left.directive_id == right.directive_id:
                    continue
                if _relation_exists(db, left.directive_id, right.directive_id, "variant_of"):
                    continue
                db.add(
                    DirectiveRelation(
                        left_directive_id=left.directive_id,
                        right_directive_id=right.directive_id,
                        relation_type="variant_of",
                        strength=0.4,
                        explanation="normalized name substring",
                    )
                )

        for directive_id, mapped_raws in touched_directives.items():
            c = db.get(CanonicalDirective, directive_id)
            if c:
                results.append(
                    CanonicalResult(
                        directive_id=directive_id,
                        preferred_name=c.preferred_name,
                        mapped_raw_count=len(mapped_raws),
                    )
                )

        log_audit(
            db,
            "directive",
            results[0].directive_id if results else raws[0].raw_directive_id,
            "canonicalized",
            {"raw_count": len(raws), "canonical_count": len(results)},
        )
        db.flush()

        return results


def canonicalize(
    db: Session,
    raw_directive_ids: list[UUID],
    *,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    embedding_search_limit: int = 10,
) -> list[CanonicalResult]:
    """Canonicalize raw directives (name match, then embedding similarity, then new canon)."""
    return Canonicalizer(
        similarity_threshold=similarity_threshold,
        embedding_model=embedding_model,
        embedding_search_limit=embedding_search_limit,
    ).canonicalize(db, raw_directive_ids)


def find_similar(
    db: Session,
    *,
    directive_id: UUID | None = None,
    query_text: str | None = None,
    limit: int = 10,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    exclude_directive_id: UUID | None = None,
) -> list[SimilarMatch]:
    """Find potential duplicate canonicals (embeddings when available, else name rules)."""
    return Canonicalizer(
        similarity_threshold=similarity_threshold,
        embedding_model=embedding_model,
    ).find_similar(
        db,
        directive_id=directive_id,
        query_text=query_text,
        limit=limit,
        exclude_directive_id=exclude_directive_id,
    )
