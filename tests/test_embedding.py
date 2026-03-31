from __future__ import annotations

import uuid

import pytest

from dkb_runtime.models import CanonicalDirective
from dkb_runtime.services import embedding as embedding_svc


def _unit(dim: int, idx: int) -> list[float]:
    v = [0.0] * dim
    v[idx] = 1.0
    return v


@pytest.fixture
def no_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_generate_embedding_mock_length_and_numeric(no_openai_key):
    vec = embedding_svc.generate_embedding("hello world", model="text-embedding-3-small")
    assert len(vec) == 1536
    assert all(isinstance(x, float) for x in vec)


def test_generate_embedding_mock_stable_for_same_input(no_openai_key):
    a = embedding_svc.generate_embedding("same", model="m")
    b = embedding_svc.generate_embedding("same", model="m")
    assert a == b


def test_store_and_find_similar_orders_by_cosine_distance(db):
    dim = 1536
    mname = "test-model"

    d0 = CanonicalDirective(preferred_name="e0", normalized_summary="x")
    d1 = CanonicalDirective(preferred_name="e1", normalized_summary="x")
    d2 = CanonicalDirective(preferred_name="e2", normalized_summary="x")
    db.add_all([d0, d1, d2])
    db.commit()

    q = _unit(dim, 0)
    v_far = _unit(dim, 1)
    raw_near = [0.99, 0.01] + [0.0] * (dim - 2)
    norm_n = sum(x * x for x in raw_near) ** 0.5
    v_near = [x / norm_n for x in raw_near]

    for d, vec in [(d0, q), (d1, v_far), (d2, v_near)]:
        embedding_svc.store_embedding(db, d.directive_id, vec, mname, embedding_dim=dim)
    db.commit()

    pairs = embedding_svc.find_similar(db, q, limit=10, model_name=mname)
    assert [p[0] for p in pairs[:3]] == [d0.directive_id, d2.directive_id, d1.directive_id]
    assert pairs[0][1] <= pairs[1][1] <= pairs[2][1]


def test_find_similar_to_directive_excludes_self(db):
    dim = 1536
    mname = "test-model"
    a = CanonicalDirective(preferred_name="a", normalized_summary="s")
    b = CanonicalDirective(preferred_name="b", normalized_summary="s")
    db.add_all([a, b])
    db.commit()

    va = _unit(dim, 0)
    vb = _unit(dim, 1)
    embedding_svc.store_embedding(db, a.directive_id, va, mname, embedding_dim=dim)
    embedding_svc.store_embedding(db, b.directive_id, vb, mname, embedding_dim=dim)
    db.commit()

    pairs = embedding_svc.find_similar_to_directive(db, a.directive_id, limit=5, model_name=mname)
    ids = [p[0] for p in pairs]
    assert a.directive_id not in ids
    assert b.directive_id in ids


def test_find_similar_to_directive_empty_without_embedding(db):
    d = CanonicalDirective(preferred_name="lonely", normalized_summary="s")
    db.add(d)
    db.commit()
    assert embedding_svc.find_similar_to_directive(db, d.directive_id) == []


def test_openai_path_skips_on_import_error(no_openai_key, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", str(uuid.uuid4()))

    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("no openai")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    vec = embedding_svc.generate_embedding("x", model="text-embedding-3-small")
    assert len(vec) == 1536
