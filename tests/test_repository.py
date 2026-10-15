"""AC5 soft removal + repository / validator behaviour."""
import pytest
from django.core.exceptions import ValidationError

from knowledgebase.constants import DocumentStatus
from knowledgebase.models import KnowledgeDocument
from knowledgebase.repositories import DocumentNotFound, KnowledgeDocumentRepository
from knowledgebase.validators import validate_status_transition
from tests.factories import make_document

pytestmark = [pytest.mark.mysql, pytest.mark.django_db]
repo = KnowledgeDocumentRepository()


def test_new_document_defaults_to_pending_pdf():
    doc = make_document()
    assert doc.status == DocumentStatus.PENDING and doc.source_type == "PDF" and doc.removed_at is None
    assert doc.uploaded_by == 42


def test_removed_document_is_kept_not_deleted():
    doc = make_document()
    removed = repo.mark_removed(doc.pk)
    assert removed.status == "REMOVED" and removed.removed_at is not None
    assert KnowledgeDocument.objects.filter(pk=doc.pk).exists()               # record retained (AC5)
    assert KnowledgeDocument.objects.count() == 1                             # not duplicated


def test_removed_document_excluded_from_indexing():
    keep, gone = make_document(), make_document()
    failed = make_document()
    repo.mark_removed(gone.pk)
    repo.change_status(failed.pk, "FAILED", failure_reason="no extractable text")
    assert [d.pk for d in repo.list_indexable()] == [keep.pk]


def test_indexed_documents_stay_indexable():
    doc = make_document()
    repo.change_status(doc.pk, "INDEXED")
    assert [d.pk for d in repo.list_indexable()] == [doc.pk]


def test_failed_status_stores_reason_and_other_statuses_clear_it():
    doc = make_document()
    assert repo.change_status(doc.pk, "FAILED", failure_reason="scanned PDF").failure_reason == "scanned PDF"
    assert repo.change_status(doc.pk, "PENDING").failure_reason is None


def test_removed_cannot_be_revived():
    doc = make_document()
    repo.mark_removed(doc.pk)
    with pytest.raises(ValidationError):
        repo.change_status(doc.pk, "PENDING")
    assert repo.get(doc.pk).status == "REMOVED"


def test_removing_twice_is_idempotent_and_keeps_first_timestamp():
    doc = make_document()
    first = repo.mark_removed(doc.pk).removed_at
    assert repo.mark_removed(doc.pk).removed_at == first


def test_invalid_status_rejected_by_repository():
    doc = make_document()
    with pytest.raises(ValidationError):
        repo.change_status(doc.pk, "DELETED")
    with pytest.raises(ValidationError):
        repo.list_by_status("nope")


def test_unknown_id_raises_not_found():
    with pytest.raises(DocumentNotFound):
        repo.get(999999)
    with pytest.raises(DocumentNotFound):
        repo.change_status(999999, "INDEXED")


def test_bad_content_hash_rejected():
    with pytest.raises(ValidationError):
        make_document(content_hash="not-a-hash")


def test_list_by_status():
    a, b = make_document(), make_document()
    repo.change_status(b.pk, "INDEXED")
    assert [d.pk for d in repo.list_by_status("PENDING")] == [a.pk]


def test_transition_validator_unit():
    validate_status_transition("PENDING", "INDEXED")
    validate_status_transition("REMOVED", "REMOVED")
    with pytest.raises(ValidationError):
        validate_status_transition("REMOVED", "INDEXED")


def test_str():
    assert str(make_document(file_name="a.pdf")) == "a.pdf [PENDING]"