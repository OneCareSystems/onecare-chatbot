import logging
from collections import namedtuple

from django.conf import settings

_query_logger = logging.getLogger(__name__)
QueryLanguage = namedtuple("QueryLanguage", "language reason")

def script_counts(text):
    """(tamil_letters, latin_letters). Same Unicode ranges as detect_language() above."""
    tamil = latin = 0
    for ch in text:
        if "\u0b80" <= ch <= "\u0bff":
            tamil += 1
        elif ch.isalpha() and ord(ch) < 0x250:
            latin += 1
    return tamil, latin


def detect_query_language(query):
    """Returns QueryLanguage(language, reason). language is always "EN" or "TA". NEVER raises.
    Script share only: Tamil letters / (Tamil + Latin letters) >= CHAT_TAMIL_SHARE_THRESHOLD (default 0.5) -> TA.
    Everything else is EN, with the reason logged. Romanised Tamil (Tanglish) is Latin script, so it cannot be told
    apart from English and is deliberately EN: guardrails must not depend on this result (CHAT-02 runs all pattern sets).
    The query text itself is never logged."""
    try:
        text = (query or "").strip()
        if not text:
            result = QueryLanguage("EN", "EMPTY_QUERY_DEFAULT_EN")
        else:
            tamil, latin = script_counts(text[:2000])
            total = tamil + latin
            threshold = getattr(settings, "CHAT_TAMIL_SHARE_THRESHOLD", 0.5)
            if total == 0:
                result = QueryLanguage("EN", "NO_LETTERS_DEFAULT_EN")
            elif tamil / total >= threshold:
                result = QueryLanguage("TA", "TAMIL_SCRIPT")
            elif len(text.split()) <= 2:
                result = QueryLanguage("EN", "SHORT_QUERY_DEFAULT_EN")
            elif tamil == 0:
                result = QueryLanguage("EN", "LATIN_SCRIPT_DEFAULT_EN")     # English, or Tanglish: indistinguishable
            else:
                result = QueryLanguage("EN", "MIXED_BELOW_THRESHOLD_DEFAULT_EN")
    except Exception:
        _query_logger.exception("Language detection failed; defaulting to EN")
        result = QueryLanguage("EN", "DETECTOR_ERROR_DEFAULT_EN")
    _query_logger.info("query language decision language=%s reason=%s", result.language, result.reason)
    return result

def detect_language(text):
    """Returns (language, needs_review). Decided on the extracted text, never on the filename."""
    tamil = latin = 0
    for ch in text[:20000]:
        if "\u0b80" <= ch <= "\u0bff":
            tamil += 1
        elif ch.isalpha() and ord(ch) < 0x250:
            latin += 1
    total = tamil + latin
    if total == 0:
        return "UNKNOWN", True
    if tamil / total >= settings.KB_LANG_DOMINANCE:
        return "TA", False
    if latin / total >= settings.KB_LANG_DOMINANCE:
        return "EN", False
    return "UNKNOWN", True                      # mixed: flagged for review, still indexed