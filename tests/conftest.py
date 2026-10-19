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
    
@pytest.fixture(autouse=True)
def chat_env(settings):
    from chat_pipeline import patterns, search
    settings.CHAT_PATTERNS_FILE = patterns.DEFAULT_FILE
    settings.CHAT_SCORE_THRESHOLDS = {"EN": 0.80, "TA": 0.75, "DEFAULT": 0.80}
    settings.CHAT_SEARCH_K, settings.CHAT_SEARCH_MAX_K, settings.CHAT_SEARCH_TIMEOUT_SECONDS = 5, 10, 1
    settings.CHAT_MAX_QUERY_CHARS = 500
    settings.CHAT_TAMIL_SHARE_THRESHOLD = 0.5
    settings.CHAT_GENERATOR_CLASS = "chat_pipeline.generation.ExtractiveGenerator"
    settings.SPRING_BASE_URL, settings.SPRING_SERVICE_TOKEN = "http://spring.test", "spring-service-token"
    settings.SPRING_CONNECT_TIMEOUT, settings.SPRING_READ_TIMEOUT = 1, 1
    settings.CHAT_LOG_ENABLED = False                                                # CHAT-10 tests switch it on themselves
    settings.CHAT_LANGUAGE_CHECK = True
    settings.CHAT_CONTEXT_CHUNKS, settings.CHAT_CONTEXT_CHARS_PER_CHUNK = 4, 1200
    settings.CHAT_LANG_TA_MIN_SHARE, settings.CHAT_LANG_EN_MAX_SHARE = 0.30, 0.20
    settings.LLM_PROVIDER, settings.LLM_API_KEY, settings.LLM_MODEL, settings.LLM_BASE_URL = "openai_compatible", "test-key-123", "test-model", ""
    settings.LLM_MAX_TOKENS, settings.LLM_TEMPERATURE, settings.LLM_MAX_RETRIES = 400, 0.0, 1
    settings.LLM_CONNECT_TIMEOUT, settings.LLM_TIMEOUT_SECONDS, settings.LLM_RETRY_BACKOFF_SECONDS = 1, 1, 0
    patterns.reset_cache()
    search.reset_latencies()
    yield
    patterns.reset_cache()