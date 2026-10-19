import logging
import time

import pytest

from chat_pipeline import search
from chat_pipeline.errors import VectorStoreUnavailable
from knowledgebase import retrieval

from .chat_helpers import hit


def _patch(monkeypatch, fn):
    monkeypatch.setattr(retrieval, "search", fn)


def test_ac1_returns_hits_with_score_and_source_metadata_in_both_directions(monkeypatch):
    seen = []
    _patch(monkeypatch, lambda q, k=5: seen.append(q) or [hit(0.91, language="EN"), hit(0.83, source="https://who.int/x", language="TA")])
    for query in ("பாராசிட்டமால் எதற்கு", "what is paracetamol used for"):         # Tamil query and English query
        hits = search.similarity_search(query)
        assert hits[0]["score"] == 0.91 and hits[0]["source"] == "guide.pdf"
        assert {"chunk_id", "document_id", "source", "language", "text", "score"} <= set(hits[0])
    assert len(seen) == 2


def test_k_is_configurable_and_capped(monkeypatch, settings):
    ks = []
    _patch(monkeypatch, lambda q, k=5: ks.append(k) or [])
    search.similarity_search("x")
    search.similarity_search("x", k=3)
    search.similarity_search("x", k=999)
    search.similarity_search("x", k=0)
    assert ks == [5, 3, 10, 1]


def test_internal_file_paths_are_never_returned(monkeypatch):
    _patch(monkeypatch, lambda q, k=5: [hit(source="C:\\chatbot_storage\\documents\\7\\abc.pdf"), hit(source="/var/data/x/y.pdf")])
    assert [h["source"] for h in search.similarity_search("x")] == ["abc.pdf", "y.pdf"]


def test_ac2_a_vector_store_error_is_a_typed_error_not_an_empty_result(monkeypatch, caplog):
    _patch(monkeypatch, lambda q, k=5: (_ for _ in ()).throw(OSError("index file missing")))
    with caplog.at_level(logging.ERROR), pytest.raises(VectorStoreUnavailable):
        search.similarity_search("x")
    assert "Vector search failed" in caplog.text


def test_ac2_a_timeout_is_a_typed_error(monkeypatch, settings):
    settings.CHAT_SEARCH_TIMEOUT_SECONDS = 0.05
    _patch(monkeypatch, lambda q, k=5: time.sleep(0.5) or [])
    with pytest.raises(VectorStoreUnavailable):
        search.similarity_search("x")


def test_an_empty_index_still_returns_an_empty_list(monkeypatch):
    _patch(monkeypatch, lambda q, k=5: [])
    assert search.similarity_search("x") == []


def test_latency_is_recorded_and_p95_is_available(monkeypatch):
    _patch(monkeypatch, lambda q, k=5: [])
    assert search.latency_p95_ms() is None
    for _ in range(20):
        search.similarity_search("x")
    assert search.latency_p95_ms() is not None and search.latency_p95_ms() >= 0