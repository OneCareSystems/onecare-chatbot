from django.conf import settings


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