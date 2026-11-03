import logging
import re

from django.conf import settings

from .errors import AuditUnavailable, ValidationFailed
from .models import KnowledgeAuditEvent

logger = logging.getLogger(__name__)

RESOURCE = "KNOWLEDGE_DOCUMENT"
_SECRET_KEY = re.compile(r"token|secret|password|passwd|authorization|api[_-]?key|credential|cookie|content", re.IGNORECASE)
_MAX_VALUE = 200


def sanitize_details(details):
    """Keep only small flat values. Drop anything that looks like a secret, token or file content."""
    clean = {}
    service_token = getattr(settings, "CHATBOT_SERVICE_TOKEN", "")
    for key, value in (details or {}).items():
        if _SECRET_KEY.search(str(key)) or isinstance(value, (dict, list, bytes, bytearray)):
            continue
        text = str(value)[:_MAX_VALUE]
        if service_token and service_token in text:
            continue
        clean[str(key)] = text
    return clean


def record(*, action, resource_id, actor, document=None, details=None):
    """Write one audit row. Call it INSIDE the transaction of the action: if this raises, the action rolls back (fail closed)."""
    if not actor:
        raise ValidationFailed("An authenticated user is required.")
    try:
        return KnowledgeAuditEvent.objects.create(
            document=document, action=action, resource=RESOURCE, resource_id=str(resource_id),
            actor_external_id=actor, details=sanitize_details(details))
    except Exception as exc:
        logger.error("Audit write failed (action=%s resource_id=%s): %s", action, resource_id, exc)
        raise AuditUnavailable("Audit service unavailable. The action was not performed.") from exc