import logging
import hashlib

from django.conf import settings
from django.db import transaction
from django.db import IntegrityError

from . import url_safety
from .errors import Conflict

from . import audit, storage, validators
from .errors import ValidationFailed
from .models import KnowledgeAuditEvent as Audit
from .models import KnowledgeDocument as Doc
from .validators import clean_external_user_id
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)


def _require_actor(actor):
    try:
        actor = clean_external_user_id(actor)
    except ValueError:
        raise ValidationFailed("Invalid X-OneCare-User-Id.") from None
    if actor is None:
        raise ValidationFailed("An authenticated user is required.")
    return actor


def upload_pdf(*, uploaded_file, title, actor):
    actor = _require_actor(actor)
    validators.validate_pdf_upload(uploaded_file, settings.KB_MAX_UPLOAD_BYTES)
    sha256 = validators.sha256_of(uploaded_file)
    filename = validators.safe_filename(getattr(uploaded_file, "name", ""))
    doc_id = None
    try:
        with transaction.atomic():                     # row + file + audit succeed or fail together
            doc = Doc.objects.create(
                title=(title or filename)[:255], original_filename=filename, source_type=Doc.SourceType.PDF,
                status=Doc.Status.PENDING, content_sha256=sha256, created_by_external_id=actor)
            doc_id = doc.id
            doc.storage_path = storage.save_raw_pdf(doc.id, uploaded_file)
            doc.save(update_fields=["storage_path", "updated_at"])
            audit.record(action=Audit.Action.DOCUMENT_UPLOADED, resource_id=doc.id, actor=actor,
                         document=doc, details={"source_type": "PDF"})
    except Exception:
        if doc_id is not None:
            storage.delete_raw(doc_id)                 # no orphan files after a rollback
        raise
    return doc

def submit_link(*, url, actor):
    actor = _require_actor(actor)
    normalized = url_safety.validate_submission(url)               # nothing is fetched here
    url_hash = hashlib.sha256(normalized.encode()).hexdigest()
    if Doc.objects.filter(url_hash=url_hash).exists():
        raise Conflict("This link is already in the knowledge base.")
    try:
        with transaction.atomic():
            doc = Doc.objects.create(
                title=urlsplit(normalized).hostname, source_type=Doc.SourceType.WEB, status=Doc.Status.PENDING,
                source_url=normalized, url_hash=url_hash, created_by_external_id=actor)
            audit.record(action=Audit.Action.LINK_SUBMITTED, resource_id=doc.id, actor=actor, document=doc,
                         details={"source_type": "WEB", "url": url_safety.strip_query(normalized)})
    except IntegrityError as exc:                                  # two simultaneous submissions
        raise Conflict("This link is already in the knowledge base.") from exc
    return doc

# from dataclasses import dataclass

# from .repositories import KnowledgeDocumentRepository
# from .vector_index import VectorIndexRebuilder


# @dataclass(frozen=True)
# class VectorRebuildResult:
#     documents_seen: int


# def rebuild_vector_index(
#     repository: KnowledgeDocumentRepository,
#     rebuilder: VectorIndexRebuilder,
# ) -> VectorRebuildResult:
#     document_ids = [document.pk for document in repository.list_indexable()]
#     rebuilder.rebuild(document_ids)
#     return VectorRebuildResult(documents_seen=len(document_ids))
