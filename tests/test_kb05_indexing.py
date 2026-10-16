import pytest

from knowledgebase import ingestion, retrieval, vector_index
from knowledgebase.models import KnowledgeChunk, KnowledgeDocument as Doc

from .helpers import LONG_EN, new_pdf_doc

pytestmark = [pytest.mark.mysql, pytest.mark.django_db]


@pytest.fixture
def text(monkeypatch):
    monkeypatch.setattr(ingestion, "extract_pdf_text", lambda p: LONG_EN)
    return LONG_EN


def vector_files(settings):
    return list((settings.CHATBOT_STORAGE_DIR / "vectors").rglob("*.npy"))


def test_indexing_creates_vectors_that_map_back_and_sets_indexed(text):
    doc = new_pdf_doc()
    assert ingestion.ingest_document(doc.id) == "INDEXED"
    doc.refresh_from_db()
    assert doc.active_version == 1 and KnowledgeChunk.objects.filter(document=doc, version=1).exists()
    hits = retrieval.search("paracetamol dosage fever", k=3)
    assert hits and {h["document_id"] for h in hits} == {doc.id}
    assert vector_index.check_consistency()["consistent"]


def test_reindex_replaces_vectors_and_does_not_duplicate(text, settings):
    doc = new_pdf_doc()
    ingestion.ingest_document(doc.id)
    count = KnowledgeChunk.objects.filter(document=doc).count()
    assert ingestion.ingest_document(doc.id, reindex=True) == "INDEXED"
    doc.refresh_from_db()
    assert doc.active_version == 2
    assert KnowledgeChunk.objects.filter(document=doc).count() == count            # replaced, not doubled
    assert set(KnowledgeChunk.objects.filter(document=doc).values_list("version", flat=True)) == {2}
    assert len(vector_files(settings)) == 1 and len(vector_index.read_manifest()["chunk_ids"]) == count


def test_first_index_failure_leaves_no_partial_vectors_and_status_failed(text, monkeypatch, settings):
    real = vector_index.build_index
    monkeypatch.setattr(vector_index, "build_index", lambda include=(): (_ for _ in ()).throw(RuntimeError("boom")) if include else real(include))
    doc = new_pdf_doc()
    assert ingestion.ingest_document(doc.id) == "FAILED"
    assert KnowledgeChunk.objects.count() == 0 and vector_files(settings) == []
    assert vector_index.read_manifest()["chunk_ids"] == []


def test_failed_reindex_keeps_previous_vectors_intact(text, monkeypatch):
    doc = new_pdf_doc()
    ingestion.ingest_document(doc.id)
    real = vector_index.build_index
    monkeypatch.setattr(vector_index, "build_index", lambda include=(): (_ for _ in ()).throw(RuntimeError("boom")) if include else real(include))
    assert ingestion.ingest_document(doc.id, reindex=True) == "INDEXED"
    doc.refresh_from_db()
    assert doc.active_version == 1 and doc.failure_reason
    assert set(KnowledgeChunk.objects.filter(document=doc).values_list("version", flat=True)) == {1}
    assert retrieval.search("paracetamol dosage fever") and vector_index.check_consistency()["consistent"]


def test_retrieval_ignores_documents_that_are_not_indexed(text):
    doc = new_pdf_doc()
    ingestion.ingest_document(doc.id)
    Doc.objects.filter(pk=doc.id).update(status="FAILED")            # chunks still in FAISS, status says no
    assert retrieval.search("paracetamol dosage fever") == []


def test_ingesting_twice_does_not_run_twice(text):
    doc = new_pdf_doc()
    assert ingestion.ingest_document(doc.id) == "INDEXED"
    assert ingestion.ingest_document(doc.id) == "INDEXED"            # not PENDING any more: no second run
    assert Doc.objects.get(pk=doc.id).active_version == 1