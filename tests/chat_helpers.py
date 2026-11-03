from contextlib import contextmanager
from unittest import mock

from chat_pipeline import search

SAFE_TEXT = "Paracetamol is a medicine used to relieve pain and reduce fever. Ask your doctor before using it."


def hit(score=0.9, text=SAFE_TEXT, document_id=1, source="guide.pdf", language="EN"):
    return {"chunk_id": 1, "document_id": document_id, "source": source, "language": language, "text": text, "score": score}


@contextmanager
def fake_search(hits=None, error=None):
    """Replace the vector search. Yields the mock so tests can assert it was (not) called."""
    with mock.patch.object(search, "similarity_search", side_effect=error, return_value=hits or []) as patched:
        yield patched