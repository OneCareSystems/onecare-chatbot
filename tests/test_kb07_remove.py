import pytest

from knowledgebase import ingestion, retrieval, services, vector_index
from knowledgebase.models import KnowledgeChunk
from knowledgebase.models import KnowledgeDocument as Doc
from tests.fakes import FakeEmbedder

from .helpers import LONG_EN, auth, new_pdf_doc

pytestmark = [pytest.mark.mysql, pytest.mark.django_db]


@pytest.fixture
def indexed(monkeypatch):
    monkeypatch.setattr(ingestion, "extract_pdf_text", lambda p: LONG_EN)
    doc = new_pdf_doc()
    ingestion.ingest_document(doc.id)
    assert retrieval.search("paracetamol dosage fever")
    return doc


def test_delete_returns_204_and_vectors_are_unreachable(client, indexed, settings):
    r = client.delete(f"/internal/knowledge-base/{indexed.id}", **auth("7"))
    assert r.status_code == 204
    indexed.refresh_from_db()
    assert indexed.status == "REMOVED" and indexed.removed_at
    assert retrieval.search("paracetamol dosage fever") == []                       # the 'removed doc never retrieved' test
    assert KnowledgeChunk.objects.count() == 0
    assert not list((settings.CHATBOT_STORAGE_DIR / "vectors").rglob("*.npy"))
    assert not (settings.CHATBOT_STORAGE_DIR / "documents" / str(indexed.id)).exists()
    assert vector_index.read_manifest()["chunk_ids"] == []


def test_unknown_id_is_404_with_error_body(client):
    r = client.delete("/internal/knowledge-base/999999", **auth())
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_deleting_twice_is_204_both_times(client, indexed):
    assert client.delete(f"/internal/knowledge-base/{indexed.id}", **auth()).status_code == 204
    assert client.delete(f"/internal/knowledge-base/{indexed.id}", **auth()).status_code == 204


def test_defence_in_depth_status_filter_even_if_cleanup_never_ran(indexed):
    Doc.objects.filter(pk=indexed.id).update(status="REMOVED")                       # vectors still on disk
    assert retrieval.search("paracetamol dosage fever") == []


def test_removed_while_processing_is_never_activated(monkeypatch):
    monkeypatch.setattr(ingestion, "extract_pdf_text", lambda p: LONG_EN)
    doc = new_pdf_doc()

    class RemovesMidRun(FakeEmbedder):
        def embed_passages(self, texts):
            services.remove_document(doc.id, actor="7")                              # delete arrives during PROCESSING
            return super().embed_passages(texts)

    monkeypatch.setattr(ingestion, "get_embedder", lambda: RemovesMidRun())
    assert ingestion.ingest_document(doc.id) == "REMOVED"
    assert KnowledgeChunk.objects.count() == 0 and retrieval.search("paracetamol dosage fever") == []


def test_removed_link_can_be_submitted_again(client, settings, monkeypatch):
    from knowledgebase import url_safety
    settings.KB_URL_ALLOWLIST = ["who.int"]
    monkeypatch.setattr(url_safety, "_resolve", lambda host: ["93.184.216.34"])
    body = {"url": "https://who.int/page"}
    first = client.post("/internal/knowledge-base/links", body, content_type="application/json", **auth()).json()["id"]
    client.delete(f"/internal/knowledge-base/{first}", **auth())
    assert client.post("/internal/knowledge-base/links", body, content_type="application/json", **auth()).status_code == 202