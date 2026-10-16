import hashlib
import logging
from urllib.parse import urlsplit

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import storage, url_safety, vector_index
from .chunking import chunk_text
from .embedding import get_embedder
from .extraction import ExtractionFailed, extract_pdf_text, extract_web_text, validate_text
from .language import detect_language
from .models import KnowledgeChunk
from .models import KnowledgeDocument as Doc

logger = logging.getLogger(__name__)


def ingest_document(doc_id, *, reindex=False):
    """PENDING -> PROCESSING -> INDEXED | FAILED. Returns the resulting status.
    reindex=True re-embeds an INDEXED document; the old vectors stay live until the new version is active."""
    if reindex:
        doc = Doc.objects.filter(pk=doc_id, status=Doc.Status.INDEXED).first()
    else:
        claimed = Doc.objects.filter(pk=doc_id, status=Doc.Status.PENDING).update(
            status=Doc.Status.PROCESSING, failure_reason="", updated_at=timezone.now())   # atomic claim
        doc = Doc.objects.filter(pk=doc_id).first() if claimed else None
    if doc is None:
        return Doc.objects.filter(pk=doc_id).values_list("status", flat=True).first()

    last = KnowledgeChunk.objects.filter(document=doc).order_by("-version").values_list("version", flat=True).first() or 0
    version = max(last, doc.active_version) + 1
    try:
        embedder = get_embedder()
        text = _extract(doc)
        language, needs_review = detect_language(text)
        chunks = chunk_text(text, embedder.count_tokens, max_tokens=settings.KB_CHUNK_MAX_TOKENS,
                            min_tokens=settings.KB_CHUNK_MIN_TOKENS, overlap_tokens=settings.KB_CHUNK_OVERLAP_TOKENS)
        if not chunks:
            raise ExtractionFailed("No content to index.")
        vectors = embedder.embed_passages(chunks)
        _stage(doc, version, chunks, vectors, language, embedder)
        _activate(doc.id, version, language, needs_review, text)
    except ExtractionFailed as exc:
        _fail(doc.id, version, str(exc), reindex)
    except Exception:
        logger.exception("Indexing failed for document %s", doc.id)
        _fail(doc.id, version, "Indexing failed. See the service log.", reindex)
    return Doc.objects.get(pk=doc.id).status


def _extract(doc):
    if doc.source_type == Doc.SourceType.PDF:
        text = extract_pdf_text(storage.resolve(doc.storage_path))
    else:
        try:
            html = url_safety.safe_fetch(doc.source_url)       # re-validates the allowlist, IPs and every redirect
        except url_safety.FetchFailed as exc:
            raise ExtractionFailed(f"The page could not be fetched: {exc}") from exc
        text = extract_web_text(html, doc.source_url)
    return validate_text(text)


def _stage(doc, version, chunks, vectors, language, embedder):
    """Write the NEW version. It is invisible to queries until _activate() flips active_version."""
    source = doc.original_filename or url_safety.strip_query(doc.source_url or "")
    with transaction.atomic():
        KnowledgeChunk.objects.bulk_create([
            KnowledgeChunk(document=doc, version=version, position=i, text=t, token_count=embedder.count_tokens(t),
                           language=language, source=source[:2048], uploaded_by_external_id=doc.created_by_external_id)
            for i, t in enumerate(chunks)], batch_size=200)
    vector_index.save_vectors(doc.id, version, vectors)


def _activate(doc_id, version, language, needs_review, text):
    with vector_index.index_lock():
        vector_index.build_index(include=[(doc_id, version)])   # new AND old vectors are in the index: no gap
        with transaction.atomic():
            current = Doc.objects.select_for_update().get(pk=doc_id)
            active = current.status in (Doc.Status.PROCESSING, Doc.Status.INDEXED)   # REMOVED meanwhile -> never activate
            if active:
                current.status, current.active_version = Doc.Status.INDEXED, version
                current.language, current.needs_review, current.failure_reason = language, needs_review, ""
                if current.source_type == Doc.SourceType.WEB:
                    current.content_sha256 = hashlib.sha256(text.encode()).hexdigest()   # used by the deferred KB-06
                current.save()
        if active:
            KnowledgeChunk.objects.filter(document_id=doc_id).exclude(version=version).delete()
            vector_index.delete_other_versions(doc_id, keep=version)
        else:
            KnowledgeChunk.objects.filter(document_id=doc_id, version=version).delete()
            vector_index.delete_vectors(doc_id, version)
        vector_index.build_index()                              # drop the superseded vectors
    return active


def _fail(doc_id, version, reason, reindex):
    if KnowledgeChunk.objects.filter(document_id=doc_id, version=version).exists():
        with vector_index.index_lock():                         # remove partial new vectors; previous ones stay
            KnowledgeChunk.objects.filter(document_id=doc_id, version=version).delete()
            vector_index.delete_vectors(doc_id, version)
            vector_index.build_index()
    if reindex:
        Doc.objects.filter(pk=doc_id).update(failure_reason=reason[:500])       # stays INDEXED with the old vectors
    else:
        Doc.objects.filter(pk=doc_id, status=Doc.Status.PROCESSING).update(
            status=Doc.Status.FAILED, failure_reason=reason[:500], updated_at=timezone.now())