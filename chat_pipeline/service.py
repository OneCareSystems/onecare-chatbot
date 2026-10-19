"""DDP-#37 Stage 3 pipeline. Order: 1 language, 2 guardrail, 3 clinic facts, 4 search, 5 knowledge gap,
6 generation (CHAT-09, outside this stage), 7 post-generation filter.
Every failure path ends in a safe localised response. Raw LLM output never leaves this function unfiltered."""
import logging

from knowledgebase.language import detect_query_language

from . import clinic, confidence, guardrail, post_filter, search
from .errors import ClinicUnavailable, VectorStoreUnavailable
from .generation import get_generator
from .messages import get_message

logger = logging.getLogger(__name__)
ANSWER, REFUSAL, FALLBACK, CLINIC_FACT = "ANSWER", "REFUSAL", "FALLBACK", "CLINIC_FACT"


def _response(type_, language, message, **extra):
    body = {"success": True, "type": type_, "language": language, "message": message}
    body.update(extra)
    return body


def _fallback(language, reason, key="fallback"):
    return _response(FALLBACK, language, get_message(key, language), reason=reason)


def process_query(query):
    language = detect_query_language(query).language                                   # 1 CHAT-01

    if guardrail.evaluate(query).blocked:                                              # 2 CHAT-02 -> CHAT-03
        return _response(REFUSAL, language, get_message("refusal", language))

    try:                                                                               # 3 CHAT-07
        intent = clinic.detect_clinic_intent(query)
    except Exception:
        logger.exception("Clinic intent detection failed; continuing with the knowledge base")
        intent = None
    if intent:
        try:
            return _response(CLINIC_FACT, language, clinic.answer_clinic_fact(query, intent, language))
        except ClinicUnavailable:
            return _fallback(language, "CLINIC_DATA_UNAVAILABLE")                      # never a stale KB answer
        except Exception:                                                              # bad data, bug: still safe
            logger.exception("Clinic fact answer failed unexpectedly")
            return _fallback(language, "CLINIC_DATA_UNAVAILABLE")

    try:                                                                               # 4 CHAT-04
        hits = search.similarity_search(query)
    except VectorStoreUnavailable:
        return _fallback(language, "SEARCH_UNAVAILABLE", key="unavailable")            # not "no information"

    if not confidence.is_confident(hits, language):                                    # 5 CHAT-05
        return _fallback(language, "NO_CONFIDENT_MATCH")

    try:                                                                               # 6 CHAT-09 (outside Stage 3)
        generator = get_generator()
        raw = generator.generate(query, hits, language)
    except Exception:
        logger.exception("Answer generation failed")
        return _fallback(language, "GENERATION_UNAVAILABLE", key="unavailable")

    result = post_filter.filter_output(raw, language, getattr(generator, "system_prompt", None))   # 7 CHAT-06
    if not result.allowed:
        return _fallback(language, "OUTPUT_BLOCKED")

    threshold = confidence.threshold_for(language)
    sources = [{"documentId": h["document_id"], "source": h["source"], "language": h["language"],
                "score": round(h["score"], 4)} for h in hits if round(h["score"], 4) >= round(threshold, 4)]
    return _response(ANSWER, language, result.text, sources=sources)