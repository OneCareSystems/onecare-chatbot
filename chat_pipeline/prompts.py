"""CHAT-08: prompt assembly. The rules live in resources/system_prompt.txt so the doctor can review them.
Retrieved chunks and the patient question are DATA: they are wrapped in tags, cleaned so they cannot close those tags,
and the system prompt tells the model never to treat them as instructions."""
import hashlib
import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings

from knowledgebase.language import script_counts

PROMPT_VERSION = "1"                                  # bump whenever system_prompt.txt changes (it is logged by CHAT-10)
NO_ANSWER_TOKEN = "NO_ANSWER"
PROMPT_FILE = Path(__file__).parent / "resources" / "system_prompt.txt"
LANGUAGE_NAMES = {"EN": "English", "TA": "Tamil (\u0ba4\u0bae\u0bbf\u0bb4\u0bcd)"}
_TAGS = re.compile(r"<\s*/?\s*(context|source|question)\b[^>]*>", re.IGNORECASE)


@lru_cache(maxsize=1)
def base_system_prompt():
    return PROMPT_FILE.read_text(encoding="utf-8").strip()


def prompt_sha256():
    return hashlib.sha256(base_system_prompt().encode("utf-8")).hexdigest()


def clean(text):
    """Remove our own tags, then neutralise any remaining angle brackets, so data cannot break out of its block."""
    text = _TAGS.sub("", text or "").replace("\x00", "")
    return text.replace("<", "\u2039").replace(">", "\u203a").strip()


def build_user_prompt(query, hits, language):
    """Reply-language line + numbered context blocks (best chunks first) + the question."""
    max_chunks = getattr(settings, "CHAT_CONTEXT_CHUNKS", 4)
    max_chars = getattr(settings, "CHAT_CONTEXT_CHARS_PER_CHUNK", 1200)
    blocks = [f'<source id="{i}">\n{clean(hit["text"])[:max_chars]}\n</source>'
              for i, hit in enumerate(hits[:max_chunks], start=1)]
    return (f"Reply language: {LANGUAGE_NAMES.get(language, LANGUAGE_NAMES['EN'])}\n\n"
            f"<context>\n" + "\n".join(blocks) + f"\n</context>\n\n<question>\n{clean(query)}\n</question>")


def is_no_answer(text):
    """True if the model said it cannot answer ("NO_ANSWER", "no answer", "No_Answer." ...)."""
    return NO_ANSWER_TOKEN in re.sub(r"[\s_]+", "_", (text or "").upper())


def language_matches(text, expected):
    """CHAT-08 rule 4 as a check: a Tamil query must get a mostly-Tamil reply, an English query a mostly-Latin one."""
    if not getattr(settings, "CHAT_LANGUAGE_CHECK", True):
        return True
    tamil, latin = script_counts(text or "")
    total = tamil + latin
    if total == 0:
        return True
    share = tamil / total
    if expected == "TA":
        return share >= getattr(settings, "CHAT_LANG_TA_MIN_SHARE", 0.30)
    return share <= getattr(settings, "CHAT_LANG_EN_MAX_SHARE", 0.20)