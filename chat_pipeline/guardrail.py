"""CHAT-02: pre-generation guardrail. Diagnosis, dosage and prescription requests are blocked BEFORE retrieval or the LLM."""
import logging
from dataclasses import dataclass

from .patterns import first_match, load_patterns, normalize

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GuardrailDecision:
    blocked: bool
    category: str | None = None        # dosage | diagnosis | prescription | GUARDRAIL_ERROR
    pattern_set: str | None = None     # en | ta | romanised


def check_query(query):
    """Raises PatternConfigError (or anything else) if the check itself breaks. Use evaluate() in the pipeline."""
    hit = first_match(load_patterns()["pre_generation"], normalize(query))
    if hit:
        return GuardrailDecision(True, hit[0], hit[1])
    return GuardrailDecision(False)


def evaluate(query):
    """FAIL CLOSED: if the classifier errors, the request is refused, the error is logged (no query text)."""
    try:
        decision = check_query(query)
    except Exception as exc:  # noqa: BLE001
        logger.error("Guardrail classifier error (%s): request refused (fail-closed)", exc.__class__.__name__)
        return GuardrailDecision(True, "GUARDRAIL_ERROR", None)
    if decision.blocked:
        logger.info("Guardrail triggered category=%s set=%s", decision.category, decision.pattern_set)
    return decision