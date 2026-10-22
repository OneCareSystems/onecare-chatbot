"""DDP-#37 + DDP-#38 pipeline. Order: 1 language, 2 guardrail, 3 clinic facts, 4 search, 5 knowledge gap,
6 LLM generation (CHAT-08 prompt, CHAT-09 call), 7 post-generation filter. CHAT-10 logs every request at the end.
Every failure path ends in a safe localised response. process_query() NEVER raises."""
import logging
import time
import uuid
from dataclasses import dataclass, field

from django.conf import settings

from knowledgebase.language import detect_query_language

from . import chat_log, clinic, confidence, fixed_answers, guardrail, post_filter, prompts, search
from .errors import ClinicUnavailable, VectorStoreUnavailable
from .generation import get_generator
from .messages import get_message

logger = logging.getLogger(__name__)
ANSWER, REFUSAL, FALLBACK, CLINIC_FACT = "ANSWER", "REFUSAL", "FALLBACK", "CLINIC_FACT"
MAX_SOURCES = 3


@dataclass
class Trace:
    """What happened to one request. Filled by the pipeline, stored by CHAT-10."""
    language: str = "EN"
    language_reason: str = ""
    guardrail_category: str | None = None
    best_score: float | None = None
    hits: list = field(default_factory=list)
    model: str = ""
    prompt_version: str = ""


def _response(type_, language, message, **extra):
    body = {"success": True, "type": type_, "language": language, "message": message}
    body.update(extra)
    return body


def _fallback(language, reason, key="fallback"):
    return _response(FALLBACK, language, get_message(key, language), reason=reason)


def _sources(usable):
    """Cited documents = the documents whose chunks were given to the model, best first, one entry per document.
    Chosen by the code, never by the LLM, so a citation can never be invented. `url` is set for web sources only."""
    seen, sources = set(), []
    for hit in sorted(usable, key=lambda h: h["score"], reverse=True):
        if hit["document_id"] in seen:
            continue
        seen.add(hit["document_id"])
        source = hit["source"] or ""
        sources.append({"documentId": hit["document_id"], "source": source,
                        "url": source if source.lower().startswith(("http://", "https://")) else None,
                        "language": hit["language"], "score": round(hit["score"], 4)})
    return sources[:MAX_SOURCES]


def _run(query, trace):
    detected = detect_query_language(query)                                            # 1 CHAT-01
    language, trace.language, trace.language_reason = detected.language, detected.language, detected.reason

    decision = guardrail.evaluate(query)                                               # 2 CHAT-02 -> CHAT-03
    if decision.blocked:
        trace.guardrail_category = decision.category
        return _response(REFUSAL, language, get_message("refusal", language))

    fixed = fixed_answers.answer(query, language)
    if fixed:
        return _response(CLINIC_FACT, language, **fixed)

    try:                                                                               # 3 CHAT-07
        intent = None if fixed_answers.mentions_other_clinic(query) else clinic.detect_clinic_intent(query)
    except Exception:
        logger.exception("Clinic intent detection failed; continuing with the knowledge base")
        intent = None
    if intent:
        try:
            return _response(CLINIC_FACT, language, clinic.answer_clinic_fact(query, intent, language))
        except ClinicUnavailable:
            return _fallback(language, "CLINIC_DATA_UNAVAILABLE")                      # never a stale KB answer
        except Exception:
            logger.exception("Clinic fact answer failed unexpectedly")
            return _fallback(language, "CLINIC_DATA_UNAVAILABLE")

    try:                                                                               # 4 CHAT-04
        hits = search.similarity_search(query)
    except VectorStoreUnavailable:
        return _fallback(language, "SEARCH_UNAVAILABLE", key="unavailable")            # not "no information"
    threshold = confidence.threshold_for(language)
    trace.best_score = confidence.best_score(hits)
    trace.hits = [{"chunkId": h["chunk_id"], "documentId": h["document_id"], "source": h["source"], "language": h["language"],
                   "score": round(h["score"], 4), "used": round(h["score"], 4) >= round(threshold, 4)} for h in hits]

    if not confidence.is_confident(hits, language):                                    # 5 CHAT-05
        return _fallback(language, "NO_CONFIDENT_MATCH")
    usable = [h for h in hits if round(h["score"], 4) >= round(threshold, 4)]          # only confident chunks reach the LLM
    usable = usable[:max(1, getattr(settings, 'CHAT_CONTEXT_CHUNKS', 4))]             # citations match supplied context

    try:                                                                               # 6 CHAT-08 prompt + CHAT-09 call
        generator = get_generator()
        info = getattr(generator, "info", {}) or {}
        trace.model, trace.prompt_version = info.get("model", ""), info.get("prompt_version", "")
        raw = generator.generate(query, usable, language)
    except Exception as exc:  # noqa: BLE001 - generator failures require a safe fallback without logging patient text.
        logger.error("Answer generation failed (%s)", exc.__class__.__name__)
        return _fallback(language, "GENERATION_UNAVAILABLE", key="unavailable")

    if prompts.is_no_answer(raw):                                                      # the model says the context lacks it
        return _fallback(language, "MODEL_NO_ANSWER")
    if not prompts.language_matches(raw, language):                                    # answered in the wrong language
        return _fallback(language, "LANGUAGE_MISMATCH")

    result = post_filter.filter_output(raw, language, getattr(generator, "system_prompt", None))   # 7 CHAT-06
    if not result.allowed:
        return _fallback(language, "OUTPUT_BLOCKED")
    return _response(ANSWER, language, result.text, sources=_sources(usable))


def _fallback_path(response, trace):
    """CHAT-10: which fallback path was taken. None = a normal ANSWER or CLINIC_FACT."""
    if response["type"] == REFUSAL:
        return "GUARDRAIL_ERROR" if trace.guardrail_category == "GUARDRAIL_ERROR" else "GUARDRAIL_REFUSAL"
    if response["type"] == FALLBACK:
        return response.get("reason")
    return None


def process_query(query):
    started, request_id, trace = time.perf_counter(), uuid.uuid4().hex, Trace()
    try:
        response = _run(query, trace)
    except Exception:                                                                  # last line of defence
        logger.exception("Pipeline error")
        response = _fallback(trace.language, "PIPELINE_ERROR", key="unavailable")
    response["requestId"] = request_id
    chat_log.record(request_id, query, response, trace, _fallback_path(response, trace),
                    (time.perf_counter() - started) * 1000)                            # 10 CHAT-10 (never raises)
    return response
