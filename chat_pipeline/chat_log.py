"""CHAT-10: audit log writer. Decision: a failed log write must NOT stop the patient getting an answer. It is logged as an
ERROR and the response is returned (fail-open). Confirm this choice with the team."""
import logging
import re

from django.conf import settings
from django.db import transaction

from .models import ChatLog

logger = logging.getLogger(__name__)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_NIC = re.compile(r"\b\d{9}[vVxX]\b|\b\d{12}\b")                           # Sri Lankan NIC (old and new)
_NUMBER = re.compile(r"\+?\d[\d\s\-()]{7,}\d")                              # phone numbers and other long digit runs


def redact(text):
    text = _EMAIL.sub("[EMAIL]", text or "")
    text = _NIC.sub("[ID]", text)
    return _NUMBER.sub("[NUMBER]", text)


def _prepare(text):
    if getattr(settings, "CHAT_LOG_REDACT", True):
        text = redact(text)
    return (text or "")[:getattr(settings, "CHAT_LOG_MAX_CHARS", 4000)]


def record(request_id, query, response, trace, fallback_path, latency_ms):
    """Never raises."""
    if not getattr(settings, "CHAT_LOG_ENABLED", True):
        return
    try:
        with transaction.atomic():
            ChatLog.objects.create(
                request_id=request_id, query_text=_prepare(query), response_text=_prepare(response.get("message", "")),
                response_type=response["type"], detected_language=trace.language, language_reason=trace.language_reason,
                fallback_path=fallback_path, guardrail_category=trace.guardrail_category, best_score=trace.best_score,
                matched_chunks=trace.hits, llm_model=trace.model, prompt_version=trace.prompt_version,
                latency_ms=int(latency_ms))
    except Exception as exc:  # noqa: BLE001 - audit failures must never interrupt a response; log only the error type.
        logger.error("Chat log write failed (%s); the response is still returned", exc.__class__.__name__)
