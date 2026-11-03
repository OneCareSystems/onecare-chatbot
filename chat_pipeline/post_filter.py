"""CHAT-06: every LLM answer is checked before it is returned. Blocked or failed -> the caller returns the CHAT-05 fallback."""
import logging
import string
from dataclasses import dataclass
from datetime import UTC, datetime

from .patterns import first_match, load_patterns, normalize

logger = logging.getLogger(__name__)
SHINGLE_WORDS = 8
_STRIP = string.punctuation + "\u201c\u201d\u2018\u2019"


@dataclass(frozen=True)
class FilterResult:
    allowed: bool
    text: str | None          # the unchanged LLM text when allowed, otherwise None
    rule: str | None = None   # PROMPT_LEAK | DOSAGE | DIAGNOSIS | OFF_SCOPE | EMPTY_OUTPUT | FILTER_ERROR


def _words(text):
    return [w for w in (token.strip(_STRIP) for token in normalize(text).split()) if w]


def _leaks_system_prompt(output, system_prompt):
    """True if any run of 8 consecutive words of the system prompt appears in the output."""
    prompt_words = _words(system_prompt)
    if not prompt_words:
        return False
    size = min(SHINGLE_WORDS, len(prompt_words))
    joined_output = " " + " ".join(_words(output)) + " "
    return any(" " + " ".join(prompt_words[i:i + size]) + " " in joined_output for i in range(len(prompt_words) - size + 1))


def _check(text, system_prompt):
    patterns = load_patterns()
    normalized = normalize(text)
    if not normalized:
        return "EMPTY_OUTPUT"
    if any(marker in normalized for marker in patterns["prompt_leak_markers"]) or _leaks_system_prompt(text, system_prompt):
        return "PROMPT_LEAK"
    hit = first_match(patterns["output"], normalized)       # reuses the shared pattern file; all sets, any language
    if hit:
        return hit[0].upper()
    if any(p.search(normalized) for p in patterns["off_scope"]):
        return "OFF_SCOPE"
    return None


def filter_output(text, language, system_prompt=None):
    """FAIL CLOSED: if the filter itself errors the output is blocked. The log has rule, language and time only."""
    try:
        rule = _check(text, system_prompt)
    except Exception as exc:  # noqa: BLE001
        logger.error("Post-generation filter error (%s): output blocked (fail-closed)", exc.__class__.__name__)
        rule = "FILTER_ERROR"
    if rule:
        logger.warning("Output blocked rule=%s language=%s at=%s", rule, language, datetime.now(UTC).isoformat())
        return FilterResult(False, None, rule)
    return FilterResult(True, text)