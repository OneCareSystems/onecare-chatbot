import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from knowledgebase.models import KnowledgeDocument as Doc

from .helpers import TOKEN, auth, pdf_file
from .pdfs import english_pdf

pytestmark = [pytest.mark.mysql, pytest.mark.django_db]
URL = "/internal/knowledge-base"


def test_valid_pdf_returns_201_stores_file_and_creates_pending_row(client, settings):
    r = client.post(URL, {"file": pdf_file(), "title": "Guide"}, **auth("42"))
    assert r.status_code == 201
    doc = Doc.objects.get(pk=r.json()["id"])
    assert doc.status == "PENDING" and doc.source_type == "PDF" and doc.created_by_external_id == "42"
    assert (settings.CHATBOT_STORAGE_DIR / doc.storage_path).is_file()
    assert r.json()["uploadedBy"] == "42"


def test_non_pdf_renamed_pdf_is_rejected_with_error_body(client, settings):
    fake = SimpleUploadedFile("evil.pdf", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "application/pdf")
    r = client.post(URL, {"file": fake}, **auth())
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert Doc.objects.count() == 0 and not list((settings.CHATBOT_STORAGE_DIR / "documents").glob("*"))


def test_size_exactly_at_limit_is_accepted_and_one_byte_over_is_rejected(client, settings):
    data = english_pdf("size boundary")
    settings.KB_MAX_UPLOAD_BYTES = len(data)
    assert client.post(URL, {"file": pdf_file(data)}, **auth()).status_code == 201
    settings.KB_MAX_UPLOAD_BYTES = len(data) - 1
    assert client.post(URL, {"file": pdf_file(data)}, **auth()).status_code == 400


def test_missing_token_is_401_and_missing_user_header_is_400(client):
    assert client.post(URL, {"file": pdf_file()}).status_code == 401
    r = client.post(URL, {"file": pdf_file()}, HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert r.status_code == 400