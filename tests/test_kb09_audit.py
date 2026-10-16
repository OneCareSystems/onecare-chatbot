import json
import logging

import pytest

from knowledgebase import audit, ingestion, url_safety
from knowledgebase.models import KnowledgeAuditEvent
from knowledgebase.models import KnowledgeDocument as Doc

from .helpers import LONG_EN, TOKEN, auth, new_pdf_doc, pdf_file

pytestmark = [pytest.mark.mysql, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _links(settings, monkeypatch):
    settings.KB_URL_ALLOWLIST = ["who.int"]
    monkeypatch.setattr(url_safety, "_resolve", lambda host: ["93.184.216.34"])


class Boom:                                            # an audit store that is down
    class objects:
        @staticmethod
        def create(**kwargs):
            raise RuntimeError("audit database down")


def do_upload(client, user="42"):
    return client.post("/internal/knowledge-base", {"file": pdf_file()}, **auth(user))


def do_link(client, user="42"):
    return client.post("/internal/knowledge-base/links", {"url": "https://who.int/page?key=SECRET123"},
                       content_type="application/json", **auth(user))


def test_upload_link_and_removal_each_write_an_audit_row_with_actor_and_timestamp(client):
    doc_id = do_upload(client).json()["id"]
    link_id = do_link(client, user="43").json()["id"]
    client.delete(f"/internal/knowledge-base/{doc_id}", **auth("44"))
    rows = {(e.action, e.resource_id): e for e in KnowledgeAuditEvent.objects.all()}
    assert set(rows) == {("DOCUMENT_UPLOADED", str(doc_id)), ("LINK_SUBMITTED", str(link_id)), ("DOCUMENT_REMOVED", str(doc_id))}
    assert rows[("DOCUMENT_UPLOADED", str(doc_id))].actor_external_id == "42"
    assert rows[("LINK_SUBMITTED", str(link_id))].actor_external_id == "43"
    assert rows[("DOCUMENT_REMOVED", str(doc_id))].actor_external_id == "44"
    assert all(e.resource == "KNOWLEDGE_DOCUMENT" and e.created_at for e in rows.values())


def test_doctor_upload_audit_row_has_the_fields_and_no_token_or_secret(client):
    do_upload(client, user="42")
    row = KnowledgeAuditEvent.objects.get()
    dump = json.dumps({"a": row.actor_external_id, "x": row.action, "r": row.resource, "i": row.resource_id,
                       "d": row.details, "t": row.created_at.isoformat()})
    assert row.actor_external_id == "42" and row.action and row.resource and row.resource_id and row.created_at
    assert TOKEN not in dump and "Bearer" not in dump and "password" not in dump.lower()


def test_link_audit_never_stores_the_query_string(client):
    do_link(client)
    assert "SECRET123" not in json.dumps(KnowledgeAuditEvent.objects.get().details)


def test_sanitize_details_drops_secrets_and_nested_values(settings):
    cleaned = audit.sanitize_details({"source_type": "PDF", "authorization": "Bearer x", "api_key": "k",
                                      "file_content": "abc", "nested": {"a": 1}, "note": TOKEN, "n": "x" * 500})
    assert set(cleaned) == {"source_type", "n"} and len(cleaned["n"]) == 200


def test_upload_fails_closed_when_audit_is_down(client, monkeypatch, caplog, settings):
    monkeypatch.setattr("knowledgebase.audit.KnowledgeAuditEvent", Boom)
    with caplog.at_level(logging.ERROR):
        r = do_upload(client)
    assert r.status_code == 503 and r.json()["error"]["code"] == "AUDIT_UNAVAILABLE"
    assert Doc.objects.count() == 0 and not list((settings.CHATBOT_STORAGE_DIR / "documents").glob("*"))
    assert "Audit write failed" in caplog.text


def test_link_fails_closed_when_audit_is_down(client, monkeypatch, caplog):
    monkeypatch.setattr("knowledgebase.audit.KnowledgeAuditEvent", Boom)
    with caplog.at_level(logging.ERROR):
        assert do_link(client).status_code == 503
    assert Doc.objects.count() == 0 and "Audit write failed" in caplog.text


def test_removal_fails_closed_when_audit_is_down(client, monkeypatch, caplog):
    monkeypatch.setattr(ingestion, "extract_pdf_text", lambda p: LONG_EN)
    doc = new_pdf_doc()
    ingestion.ingest_document(doc.id)
    monkeypatch.setattr("knowledgebase.audit.KnowledgeAuditEvent", Boom)
    with caplog.at_level(logging.ERROR):
        assert client.delete(f"/internal/knowledge-base/{doc.id}", **auth()).status_code == 503
    doc.refresh_from_db()
    assert doc.status == "INDEXED" and doc.chunks.exists() and "Audit write failed" in caplog.text