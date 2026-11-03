"""Loads and validates config/guardrail_patterns.json. One file feeds CHAT-02, CHAT-06 and CHAT-07."""
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from django.conf import settings

from .errors import PatternConfigError

DEFAULT_FILE = Path(__file__).parent / "config" / "guardrail_patterns.json"
SETS = ("en", "ta", "romanised")


def normalize(text):
    """NFC, straight apostrophes, one-space whitespace, case-folded. Applied to every text before matching."""
    text = unicodedata.normalize("NFC", text or "")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"\s+", " ", text).strip().casefold()


def _compile(name, patterns, allow_empty=False):
    if not isinstance(patterns, list) or (not patterns and not allow_empty):
        raise PatternConfigError(f"{name}: a non-empty list of patterns is required")
    compiled = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern, re.IGNORECASE))
        except (re.error, TypeError) as exc:
            raise PatternConfigError(f"{name}: invalid pattern ({exc})") from exc
    return compiled


def _groups(raw, section, categories, allow_empty_sets=()):
    block = raw.get(section)
    if not isinstance(block, dict):
        raise PatternConfigError(f"Section '{section}' is missing")
    groups = {}
    for category in categories:
        sets = block.get(category)
        if not isinstance(sets, dict):
            raise PatternConfigError(f"{section}.{category} is missing")
        groups[category] = {
            name: _compile(f"{section}.{category}.{name}", sets.get(name), allow_empty=name in allow_empty_sets)
            for name in SETS}
    return groups


@lru_cache(maxsize=4)
def _load(path):
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PatternConfigError(f"Pattern file cannot be read ({exc.__class__.__name__})") from exc
    if not isinstance(raw, dict):
        raise PatternConfigError("Pattern file must contain a JSON object")
    markers = raw.get("prompt_leak_markers")
    if not isinstance(markers, list) or not all(isinstance(m, str) for m in markers):
        raise PatternConfigError("prompt_leak_markers must be a list of strings")
    return {
        "pre_generation": _groups(raw, "pre_generation", ("dosage", "diagnosis", "prescription")),
        "output": _groups(raw, "output", ("dosage", "diagnosis"), allow_empty_sets=("romanised",)),
        "off_scope": _compile("off_scope", raw.get("off_scope")),
        "prompt_leak_markers": [normalize(m) for m in markers if m.strip()],
        "clinic_facts": {
            "hours": _groups({"c": {"hours": raw.get("clinic_facts", {}).get("hours")}}, "c", ("hours",))["hours"],
            "availability": _groups({"c": {"availability": raw.get("clinic_facts", {}).get("availability")}}, "c",
                                    ("availability",))["availability"],
            "today": _compile("clinic_facts.today", raw.get("clinic_facts", {}).get("today")),
            "tomorrow": _compile("clinic_facts.tomorrow", raw.get("clinic_facts", {}).get("tomorrow")),
        },
    }


def load_patterns():
    return _load(str(getattr(settings, "CHAT_PATTERNS_FILE", DEFAULT_FILE)))


def reset_cache():
    _load.cache_clear()


def first_match(groups, text):
    """groups = {category: {set_name: [compiled]}}. EVERY set (en, ta, romanised) is tried: the detected language is
    never used to choose a set. Returns (category, set_name) of the first hit, or None."""
    for category, sets in groups.items():
        for set_name, compiled in sets.items():
            if any(pattern.search(text) for pattern in compiled):
                return category, set_name
    return None