from django.utils import timezone

from .constants import INDEXABLE_STATUSES, DocumentStatus
from .models import KnowledgeDocument
from .validators import validate_status, validate_status_transition


class DocumentNotFound(Exception):
    """Raised when a document id does not exist."""


class KnowledgeDocumentRepository:
    def create(self, **fields):
        document = KnowledgeDocument(**fields)
        document.save()
        return document

    def get(self, document_id):
        try:
            return KnowledgeDocument.objects.get(pk=document_id)
        except KnowledgeDocument.DoesNotExist as exc:
            raise DocumentNotFound(f"Knowledge document {document_id} was not found.") from exc

    def change_status(self, document_id, status, *, failure_reason=None):
        document = self.get(document_id)
        validate_status_transition(document.status, status)
        document.status = status
        document.failure_reason = failure_reason if status == DocumentStatus.FAILED else None
        if status == DocumentStatus.REMOVED:
            document.removed_at = document.removed_at or timezone.now()
        else:
            document.removed_at = None
        document.save()
        return document

    def mark_removed(self, document_id):
        return self.change_status(document_id, DocumentStatus.REMOVED)

    def list_by_status(self, status):
        validate_status(status)
        return KnowledgeDocument.objects.filter(status=status).order_by("pk")

    def list_indexable(self):
        return KnowledgeDocument.objects.filter(status__in=INDEXABLE_STATUSES).order_by("pk")
