import re
import unicodedata

from django.conf import settings

_PUA = re.compile(r"[\ue000-\uf8ff]")          # private-use glyphs: legacy fonts that do not map to Unicode
_CID = re.compile(r"\(cid:\d+\)")              # pdf glyphs with no Unicode mapping


class ExtractionFailed(Exception):
    """The document cannot be turned into usable text. The message becomes failure_reason."""


def extract_pdf_text(path):
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception as exc:
        raise ExtractionFailed(f"The PDF could not be read ({exc.__class__.__name__}).") from exc


def extract_web_text(html, url):
    import trafilatura
    return trafilatura.extract(html, url=url, include_comments=False, include_tables=True) or ""


def validate_text(text):
    text = unicodedata.normalize("NFC", text or "").strip()
    if len(text) < settings.KB_MIN_TEXT_CHARS:
        raise ExtractionFailed("No extractable text (a scanned PDF or an empty page). OCR is not supported.")
    broken = text.count("\ufffd") + len(_PUA.findall(text)) + len(_CID.findall(text))
    if broken / len(text) > 0.01:
        raise ExtractionFailed("The text is unreadable (broken glyphs or fonts without Unicode mapping).")
    return text