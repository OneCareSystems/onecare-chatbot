"""AC2 valid statuses, AC3 invalid statuses rejected BY THE DATABASE, source_type must be PDF."""
import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction

from knowledgebase.constants import DocumentStatus
from knowledgebase.models import KnowledgeDocument
from tests.factories import RAW_INSERT, make_document

pytestmark = [pytest.mark.mysql, pytest.mark.django_db]

BAD_STATUSES = ["DELETED", "pending", "Pending", "PENDING ", "", "INDEXED;", "ACTIVE"]


def assert_db_rejects(action):
    """MySQL error 3819 = CHECK constraint violated. Wrapped in atomic() so the test can continue."""
    with pytest.raises(DatabaseError) as exc, transaction.atomic():
        action()
    assert "3819" in str(exc.value) or "check constraint" in str(exc.value).lower()


@pytest.mark.parametrize("status", DocumentStatus.values)
def test_each_valid_status_persists(status):
    doc = make_document(status=status)
    assert KnowledgeDocument.objects.get(pk=doc.pk).status == status


@pytest.mark.parametrize("bad", BAD_STATUSES)
def test_invalid_status_rejected_on_update_by_database(bad):
    doc = make_document()
    # .update() skips model.save(), so only the DB CHECK constraint can stop this
    assert_db_rejects(lambda: KnowledgeDocument.objects.filter(pk=doc.pk).update(status=bad))


@pytest.mark.parametrize("bad", BAD_STATUSES)
def test_invalid_status_rejected_on_insert_via_raw_sql(bad):
    def run():
        with connection.cursor() as c:
            c.execute(RAW_INSERT, ["PDF", bad])
    assert_db_rejects(run)


def test_invalid_status_rejected_on_update_via_raw_sql():
    doc = make_document()

    def run():
        with connection.cursor() as c:
            c.execute("UPDATE knowledge_document SET status = %s WHERE id = %s", ["DELETED", doc.pk])
    assert_db_rejects(run)


def test_invalid_status_rejected_by_bulk_create():
    bad = KnowledgeDocument(file_name="b.pdf", storage_path="p", content_hash="a" * 64,
                            uploaded_by=1, status="DELETED")
    assert_db_rejects(lambda: KnowledgeDocument.objects.bulk_create([bad]))      # bulk_create skips save()


def test_application_layer_also_rejects_invalid_status():
    with pytest.raises(ValidationError):
        make_document(status="DELETED")
    with pytest.raises(ValidationError):
        KnowledgeDocument(file_name="x.pdf", storage_path="p", content_hash="a" * 64,
                          uploaded_by=1, status="nope").save()


@pytest.mark.parametrize("bad", ["DOCX", "pdf", "WEB", "PDF ", ""])
def test_source_type_other_than_pdf_rejected_by_database(bad):
    def run():
        with connection.cursor() as c:
            c.execute(RAW_INSERT, [bad, "PENDING"])
    assert_db_rejects(run)


def test_source_type_pdf_accepted_via_raw_sql():
    with connection.cursor() as c:
        c.execute(RAW_INSERT, ["PDF", "PENDING"])
    assert KnowledgeDocument.objects.filter(file_name="raw.pdf").count() == 1


def test_language_must_be_en_ta_or_null():
    assert make_document(language=None).language is None
    assert make_document(language="ta").language == "ta"
    doc = make_document()
    assert_db_rejects(lambda: KnowledgeDocument.objects.filter(pk=doc.pk).update(language="fr"))