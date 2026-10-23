from types import SimpleNamespace
from unittest.mock import patch

import pytest

from .helpers import auth


def test_saved_pdf_can_be_viewed_and_downloaded(client, settings):
    # Opening a stored file does not depend on its upload date or ingestion status.
    path = settings.CHATBOT_STORAGE_DIR / "saved.pdf"
    path.write_bytes(b"%PDF-1.4\noriginal bytes")
    doc = SimpleNamespace(storage_path="saved.pdf", original_filename="guide.pdf")
    with patch("knowledgebase.views.KnowledgeDocument.objects") as objects:
        objects.filter.return_value.exclude.return_value.first.return_value = doc
        response = client.get("/internal/knowledge-base/7/file", **auth())
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert response["Content-Disposition"].startswith("inline;")
        assert b"".join(response.streaming_content) == path.read_bytes()
        response.close()
        response = client.get("/internal/knowledge-base/7/file?download=1", **auth())
        assert response["Content-Disposition"].startswith("attachment;")
        response.close()


@pytest.mark.parametrize("headers,status", [({}, 401), (auth(None), 400)])
def test_file_requires_service_and_actor(client, headers, status):
    assert client.get("/internal/knowledge-base/7/file", **headers).status_code == status


def test_removed_or_missing_pdf_is_not_available(client):
    with patch("knowledgebase.views.KnowledgeDocument.objects") as objects:
        objects.filter.return_value.exclude.return_value.first.return_value = None
        assert client.get("/internal/knowledge-base/7/file", **auth()).status_code == 404
        objects.filter.return_value.exclude.assert_called_with(status="REMOVED")
        objects.filter.return_value.exclude.return_value.first.return_value = SimpleNamespace(
            storage_path="missing.pdf", original_filename="guide.pdf")
        assert client.get("/internal/knowledge-base/7/file", **auth()).status_code == 404
