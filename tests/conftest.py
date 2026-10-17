import importlib

import pytest

from .helpers import TOKEN


def _reset_caches():
    """embedding.py (KB-04) and the new vector_index.py (KB-05) arrive in later steps; skip until they exist."""
    for module, function in (("knowledgebase.embedding", "reset_embedder"), ("knowledgebase.vector_index", "reset_cache")):
        try:
            getattr(importlib.import_module(module), function)()
        except (ImportError, AttributeError):
            pass


@pytest.fixture(autouse=True)
def kb_env(settings, tmp_path):
    settings.CHATBOT_STORAGE_DIR = tmp_path
    settings.CHATBOT_SERVICE_TOKEN = TOKEN
    settings.KB_EMBEDDER_CLASS = "tests.fakes.FakeEmbedder"
    settings.KB_CHUNK_MAX_TOKENS, settings.KB_CHUNK_MIN_TOKENS, settings.KB_CHUNK_OVERLAP_TOKENS = 45, 30, 5
    _reset_caches()
    yield
    _reset_caches()