"""Unit tests for embedding-based dedup in canonicalizer (no database)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from dkb_runtime.models import CanonicalDirective
from dkb_runtime.services.canonicalizer import (
    Canonicalizer,
    _distance_to_cosine_similarity,
    _name_fallback_matches,
    _name_similarity_score,
    find_similar,
)


def test_distance_to_cosine_similarity():
    assert _distance_to_cosine_similarity(0.0) == 1.0
    assert _distance_to_cosine_similarity(0.15) == pytest.approx(0.85)
    assert _distance_to_cosine_similarity(1.0) == 0.0


def test_name_similarity_score_exact_and_substring():
    assert _name_similarity_score("foo", "foo") == 1.0
    assert _name_similarity_score("foo", "foobar") == pytest.approx(0.88)
    assert _name_similarity_score("foobar", "foo") == pytest.approx(0.88)
    assert _name_similarity_score("ab", "abc") is None
    assert _name_similarity_score("unrelated", "other") is None


def test_name_fallback_matches_respects_threshold():
    db = MagicMock()
    a = CanonicalDirective(preferred_name="my_tool", normalized_summary="x")
    a.directive_id = uuid4()
    b = CanonicalDirective(preferred_name="other", normalized_summary="y")
    b.directive_id = uuid4()

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [a, b]
    db.scalars.return_value = scalars_mock

    hits = _name_fallback_matches(db, "my_tool", similarity_threshold=0.85)
    assert len(hits) == 1
    assert hits[0].directive_id == a.directive_id
    assert hits[0].similarity == 1.0
    assert hits[0].match_kind == "name"


def test_find_similar_requires_exactly_one_query_source():
    db = MagicMock()
    c = Canonicalizer()
    with pytest.raises(ValueError, match="exactly one"):
        c.find_similar(db)
    with pytest.raises(ValueError, match="exactly one"):
        c.find_similar(db, directive_id=uuid4(), query_text="x")


@patch("dkb_runtime.services.canonicalizer.embedding_svc")
def test_find_similar_embedding_path_filters_by_threshold(mock_emb, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    did = uuid4()
    other = uuid4()

    canon = MagicMock(spec=CanonicalDirective)
    canon.directive_id = did
    canon.preferred_name = "alpha"

    db = MagicMock()
    db.get.return_value = canon

    third = uuid4()
    mock_emb.generate_embedding.return_value = [0.1] * 1536
    mock_emb.find_similar.return_value = [
        (other, 0.10),
        (third, 0.12),
    ]

    c = Canonicalizer(similarity_threshold=0.85)
    out = c.find_similar(db, query_text="alpha tool", limit=5)

    mock_emb.generate_embedding.assert_called_once()
    mock_emb.find_similar.assert_called_once()
    assert len(out) == 2
    assert all(m.similarity >= 0.85 for m in out)
    assert all(m.match_kind == "embedding" for m in out)
    assert {m.directive_id for m in out} == {other, third}


@patch("dkb_runtime.services.canonicalizer.embedding_svc")
def test_find_similar_excludes_directive(mock_emb, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    self_id = uuid4()

    canon = MagicMock(spec=CanonicalDirective)
    canon.directive_id = self_id
    canon.preferred_name = "solo"

    db = MagicMock()
    db.get.return_value = canon
    mock_emb.generate_embedding.return_value = [0.2] * 1536
    mock_emb.find_similar.return_value = [(self_id, 0.0), (uuid4(), 0.05)]

    c = Canonicalizer(similarity_threshold=0.85)
    out = c.find_similar(db, directive_id=self_id, limit=10)

    assert self_id not in {m.directive_id for m in out}


@patch("dkb_runtime.services.canonicalizer.embedding_svc")
def test_find_similar_name_fallback_when_embedding_empty(mock_emb, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    peer = uuid4()

    canon = MagicMock(spec=CanonicalDirective)
    canon.directive_id = uuid4()
    canon.preferred_name = "query_name"

    peer_canon = MagicMock(spec=CanonicalDirective)
    peer_canon.directive_id = peer
    peer_canon.preferred_name = "query_name_long"

    db = MagicMock()
    db.get.return_value = canon
    mock_emb.generate_embedding.return_value = [0.3] * 1536
    mock_emb.find_similar.return_value = []

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [canon, peer_canon]
    db.scalars.return_value = scalars_mock

    c = Canonicalizer(similarity_threshold=0.85)
    out = c.find_similar(db, directive_id=canon.directive_id, limit=5)

    assert any(m.directive_id == peer and m.match_kind == "name" for m in out)


@patch("dkb_runtime.services.canonicalizer.embedding_svc")
def test_canonicalize_calls_embedding_similarity_with_model(mock_emb, monkeypatch):
    """canonicalize uses embedding_svc.find_similar with the configured model name."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    existing_id = uuid4()
    existing = MagicMock(spec=CanonicalDirective)
    existing.directive_id = existing_id
    existing.preferred_name = "Existing Canon"

    raw = MagicMock()
    raw.raw_directive_id = uuid4()
    raw.raw_name = "Different Label"
    raw.summary_raw = "same purpose"
    raw.evidence_items = []

    raw_result = MagicMock()
    raw_result.all.return_value = [raw]
    canon_result = MagicMock()
    canon_result.all.return_value = [existing]
    rel_result = MagicMock()
    rel_result.limit.return_value.first.return_value = None

    db = MagicMock()
    db.scalars.side_effect = [raw_result, canon_result] + [rel_result] * 32
    db.get.return_value = existing

    mock_emb.generate_embedding.return_value = [0.5] * 1536
    mock_emb.find_similar.return_value = [(existing_id, 0.05)]

    c = Canonicalizer(
        similarity_threshold=0.85,
        embedding_model="custom-model",
        embedding_search_limit=7,
    )
    with patch("dkb_runtime.services.canonicalizer.log_audit"):
        c.canonicalize(db, [raw.raw_directive_id])

    mock_emb.find_similar.assert_called_once()
    _, kwargs = mock_emb.find_similar.call_args
    assert kwargs["model_name"] == "custom-model"
    assert kwargs["limit"] == 7
    mock_emb.store_embedding.assert_called_once()


def test_module_find_similar_delegates_to_canonicalizer():
    db = MagicMock()
    with patch.object(Canonicalizer, "find_similar", return_value=[]) as m:
        find_similar(db, query_text="x", similarity_threshold=0.9, embedding_model="m")
    m.assert_called_once()
    _, kwargs = m.call_args
    assert kwargs["query_text"] == "x"
