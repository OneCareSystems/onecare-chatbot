from . import url_safety


def document_to_dict(doc):
    return {
        "id": doc.id,
        "title": doc.title,
        "sourceType": doc.source_type,
        "status": doc.status,
        "language": doc.language or None,
        "needsReview": doc.needs_review,
        "originalFilename": doc.original_filename or None,
        "sourceUrl": url_safety.strip_query(doc.source_url) if doc.source_url else None,   # never echo query strings
        "uploadedBy": doc.created_by_external_id,
        "failureReason": doc.failure_reason or None,
        "createdAt": doc.created_at.isoformat(),
    }