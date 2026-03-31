from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from dkb_runtime.models import (
    CanonicalDirective,
    DimensionScore,
    Pack,
    Verdict,
)
from dkb_runtime.services.pack_engine import build_pack


def _canon_with_scores_and_verdict(db, dimension_model, *, trust: str, score_val: float = 0.9):
    c = CanonicalDirective(
        preferred_name=f"P-{uuid4().hex[:8]}",
        normalized_summary="review and plan",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    for group, key in [
        ("form", "skillness"),
        ("function", "review"),
        ("governance", "trustworthiness"),
        ("clarity", "description_clarity"),
    ]:
        db.add(
            DimensionScore(
                directive_id=c.directive_id,
                dimension_model_id=dimension_model.dimension_model_id,
                dimension_group=group,
                dimension_key=key,
                score=score_val,
                confidence=0.8,
                explanation="test",
            )
        )
    db.add(
        Verdict(
            directive_id=c.directive_id,
            dimension_model_id=dimension_model.dimension_model_id,
            provenance_state="unknown",
            trust_state=trust,
            legal_state="clear",
            lifecycle_state="active",
            recommendation_state="candidate",
        )
    )
    db.commit()
    return c


def test_pack_filters_by_trust_state(db, dimension_model):
    a = _canon_with_scores_and_verdict(db, dimension_model, trust="verified")
    _canon_with_scores_and_verdict(db, dimension_model, trust="blocked")

    pack = Pack(
        pack_key="tpack",
        pack_name="T",
        pack_goal="g",
        pack_type="custom",
        selection_policy={"trust_states": ["verified"], "max_items": 10},
        status="draft",
    )
    db.add(pack)
    db.commit()
    db.refresh(pack)

    result = build_pack(db, pack.pack_id)
    db.commit()
    assert result.item_count == 1
    items = db.get(Pack, pack.pack_id).items
    assert len(items) == 1
    assert items[0].directive_id == a.directive_id


def test_pack_min_scores_and_exclusion(db, dimension_model):
    hi = _canon_with_scores_and_verdict(db, dimension_model, trust="verified", score_val=0.95)
    lo = _canon_with_scores_and_verdict(db, dimension_model, trust="verified", score_val=0.1)

    pack = Pack(
        pack_key="tpack2",
        pack_name="T2",
        pack_goal="g",
        pack_type="custom",
        selection_policy={
            "trust_states": ["verified"],
            "min_scores": {"function.review": 0.8},
            "max_items": 10,
        },
        status="draft",
    )
    db.add(pack)
    db.commit()
    db.refresh(pack)

    build_pack(db, pack.pack_id)
    db.commit()
    ids = {i.directive_id for i in db.get(Pack, pack.pack_id).items}
    assert hi.directive_id in ids
    assert lo.directive_id not in ids


def test_pack_excludes_by_recommendation(db, dimension_model):
    c = _canon_with_scores_and_verdict(db, dimension_model, trust="verified")
    v = db.scalars(select(Verdict).where(Verdict.directive_id == c.directive_id)).one()
    v.recommendation_state = "excluded"
    db.add(v)
    db.commit()

    pack = Pack(
        pack_key="tpack3",
        pack_name="T3",
        pack_goal="g",
        pack_type="custom",
        selection_policy={"trust_states": ["verified"], "max_items": 10},
        status="draft",
    )
    db.add(pack)
    db.commit()
    db.refresh(pack)

    build_pack(db, pack.pack_id)
    db.commit()
    assert len(db.get(Pack, pack.pack_id).items) == 0
