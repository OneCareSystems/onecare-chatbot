"""Static, doctor-approved texts live in resources/messages_<lang>.json (NFRPO005), never in code."""
import json
from functools import cache
from pathlib import Path

RESOURCE_DIR = Path(__file__).parent / "resources"
SUPPORTED = ("EN", "TA")


@cache
def _load(language):
    return json.loads((RESOURCE_DIR / f"messages_{language.lower()}.json").read_text(encoding="utf-8"))


def normalize_language(language):
    """Anything that is not clearly TA (EN, UNKNOWN, None, garbage) is English: the CHAT-01 default."""
    return "TA" if language == "TA" else "EN"


def get_message(key, language="EN", **params):
    lang = normalize_language(language)
    text = _load(lang).get(key) or _load("EN")[key]
    return text.format(**params) if params else text


def day_name(day, language="EN"):
    days = _load(normalize_language(language)).get("days", {})
    return days.get(str(day).upper(), str(day).title())