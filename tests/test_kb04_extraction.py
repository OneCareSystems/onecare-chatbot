import pytest

from knowledgebase import ingestion
from knowledgebase.chunking import chunk_text
from knowledgebase.language import detect_language
from knowledgebase.models import KnowledgeChunk
from knowledgebase.models import KnowledgeDocument as Doc

from .helpers import LONG_EN, new_pdf_doc
from .pdfs import english_pdf, scanned_pdf, tamil_pdf

TAMIL = "காய்ச்சல் இருந்தால் மருத்துவரை அணுகவும். போதுமான ஓய்வு எடுக்கவும். " * 20


# ---- unit tests (no database) ----
def test_language_detection_en_ta_mixed_and_empty():
    assert detect_language(LONG_EN) == ("EN", False)
    assert detect_language(TAMIL) == ("TA", False)
    assert detect_language(LONG_EN[:300] + " " + TAMIL[:300]) == ("UNKNOWN", True)
    assert detect_language("12345 !!!") == ("UNKNOWN", True)


def test_chunks_respect_max_and_only_last_may_be_below_min():
    text = " ".join(f"w{i}" for i in range(2000))
    chunks = chunk_text(text, lambda t: len(t.split()), max_tokens=45, min_tokens=30, overlap_tokens=5)
    sizes = [len(c.split()) for c in chunks]
    assert all(s <= 45 for s in sizes) and all(s >= 30 for s in sizes[:-1])
    assert chunks[0].split()[-5:] == chunks[1].split()[:5]               # overlap
    assert " ".join(w for c in chunks for w in c.split()[(5 if c is not chunks[0] else 0):]).split() == text.split()


def test_an_oversized_single_word_is_split_not_looped():
    chunks = chunk_text("x" * 500, len, max_tokens=45, min_tokens=30, overlap_tokens=5)
    assert all(len(c) <= 45 for c in chunks)


# ---- pipeline tests ----
pytestmark_db = [pytest.mark.mysql, pytest.mark.django_db]


@pytest.mark.mysql
@pytest.mark.django_db
def test_tamil_pdf_is_valid_tamil_with_language_ta_and_full_chunk_metadata(monkeypatch, settings):
    doc = new_pdf_doc(actor="42")
    path = settings.CHATBOT_STORAGE_DIR / doc.storage_path
    path.write_bytes(tamil_pdf(TAMIL))                                  # skipped if the font file is missing
    assert ingestion.ingest_document(doc.id) == "INDEXED"
    doc.refresh_from_db()
    chunk = KnowledgeChunk.objects.filter(document=doc).first()
    assert doc.language == "TA" and "மருத்துவரை" in chunk.text
    assert (chunk.document_id, chunk.language, chunk.uploaded_by_external_id) == (doc.id, "TA", "42") and chunk.source


@pytest.mark.mysql
@pytest.mark.django_db
def test_scanned_pdf_fails_with_reason_and_stores_no_chunks(settings):
    doc = new_pdf_doc()
    (settings.CHATBOT_STORAGE_DIR / doc.storage_path).write_bytes(scanned_pdf())
    assert ingestion.ingest_document(doc.id) == "FAILED"
    doc.refresh_from_db()
    assert "No extractable text" in doc.failure_reason and KnowledgeChunk.objects.count() == 0


@pytest.mark.mysql
@pytest.mark.django_db
def test_mixed_language_is_unknown_flagged_and_still_indexed(monkeypatch):
    mixed = LONG_EN[:600] + " " + TAMIL[:600]
    monkeypatch.setattr(ingestion, "extract_pdf_text", lambda p: mixed)
    doc = new_pdf_doc()
    assert ingestion.ingest_document(doc.id) == "INDEXED"
    doc.refresh_from_db()
    assert doc.language == "UNKNOWN" and doc.needs_review is True and KnowledgeChunk.objects.filter(document=doc).exists()


@pytest.mark.mysql
@pytest.mark.django_db
def test_status_goes_pending_processing_failed_on_extraction_error(monkeypatch):
    seen = []
    def spy(path):
        seen.append(Doc.objects.get(source_type="PDF").status)
        return ""
    monkeypatch.setattr(ingestion, "extract_pdf_text", spy)
    doc = new_pdf_doc()
    assert doc.status == "PENDING"
    ingestion.ingest_document(doc.id)
    assert seen == ["PROCESSING"] and Doc.objects.get(pk=doc.id).status == "FAILED"


@pytest.mark.mysql
@pytest.mark.django_db
def test_english_pdf_is_extracted_and_tagged_en(settings):
    doc = new_pdf_doc()
    (settings.CHATBOT_STORAGE_DIR / doc.storage_path).write_bytes(english_pdf(LONG_EN))
    assert ingestion.ingest_document(doc.id) == "INDEXED"
    assert Doc.objects.get(pk=doc.id).language == "EN"