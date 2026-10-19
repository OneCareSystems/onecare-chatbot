"""AC3 against the REAL index (needs MySQL, like the other KB tests). Only INDEXED documents are ever returned."""
import pytest

from chat_pipeline import search
from knowledgebase import ingestion
from knowledgebase.models import KnowledgeDocument as Doc

from .helpers import LONG_EN, new_pdf_doc

pytestmark = [pytest.mark.mysql, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def direct_search(settings, monkeypatch):
    settings.CHAT_SEARCH_TIMEOUT_SECONDS = 0          # no worker thread: the test transaction must stay visible
    monkeypatch.setattr(ingestion, "extract_pdf_text", lambda p: LONG_EN)


def _indexed():
    doc = new_pdf_doc()
    assert ingestion.ingest_document(doc.id) == "INDEXED"
    return doc


def test_indexed_documents_are_returned_with_metadata():
    doc = _indexed()
    hits = search.similarity_search("paracetamol dosage fever")
    assert hits and {h["document_id"] for h in hits} == {doc.id}
    assert hits[0]["source"] == "doc.pdf" and hits[0]["score"] > 0


@pytest.mark.parametrize("status", ["REMOVED", "FAILED", "PENDING"])
def test_ac3_documents_that_are_not_indexed_are_never_returned(status):
    doc = _indexed()
    Doc.objects.filter(pk=doc.id).update(status=status)
    assert search.similarity_search("paracetamol dosage fever") == []