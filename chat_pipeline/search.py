"""CHAT-04: similarity search over INDEXED chunks (EN and TA, PDF and web). Wraps knowledgebase.retrieval.search,
which already filters status=INDEXED and the active index version and uses the SAME embedder as KB-05."""
import logging
import os
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from django.conf import settings
from django.db import connection

from knowledgebase import retrieval

from .errors import VectorStoreUnavailable

logger = logging.getLogger(__name__)
_latencies = deque(maxlen=500)
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="chat-search")


def clamp_k(k=None):
    default = getattr(settings, "CHAT_SEARCH_K", 5)
    maximum = max(1, getattr(settings, "CHAT_SEARCH_MAX_K", 10))
    return max(1, min(int(k if k is not None else default), maximum))


def _safe_source(source):
    """A filename or a URL without a query string. Never a server path."""
    source = (source or "")[:2048]
    if source.lower().startswith(("http://", "https://")):
        return source
    return os.path.basename(source.replace("\\", "/"))


def _public_hit(hit):
    return {"chunk_id": hit["chunk_id"], "document_id": hit["document_id"], "source": _safe_source(hit.get("source")),
            "language": hit.get("language"), "text": hit["text"], "score": float(hit["score"])}


def _worker(query, k):
    try:
        return retrieval.search(query, k=k)
    finally:
        connection.close()                      # this thread opened its own DB connection


def latency_p95_ms():
    """Nearest-rank p95 of the last 500 searches, or None."""
    if not _latencies:
        return None
    ordered = sorted(_latencies)
    return ordered[max(0, -(-95 * len(ordered) // 100) - 1)]


def reset_latencies():
    _latencies.clear()


def similarity_search(query, k=None):
    """Top-k hits as [{chunk_id, document_id, source, language, text, score}], best first.
    Vector store failure or timeout raises VectorStoreUnavailable. It is NEVER returned as [], so CHAT-05 cannot
    report a false 'no information'. An empty list means the index really has nothing."""
    k = clamp_k(k)
    timeout = getattr(settings, "CHAT_SEARCH_TIMEOUT_SECONDS", 5)
    started = time.perf_counter()
    try:
        if timeout and timeout > 0:
            hits = _executor.submit(_worker, query, k).result(timeout=timeout)
        else:
            hits = retrieval.search(query, k=k)
    except FutureTimeout as exc:
        logger.error("Vector search timed out after %ss", timeout)
        raise VectorStoreUnavailable("The vector search timed out.") from exc
    except Exception as exc:
        logger.error("Vector search failed (%s)", exc.__class__.__name__)
        raise VectorStoreUnavailable("The vector search failed.") from exc
    elapsed_ms = (time.perf_counter() - started) * 1000
    _latencies.append(elapsed_ms)
    logger.info("search latency_ms=%.1f k=%d hits=%d", elapsed_ms, k, len(hits))
    return [_public_hit(hit) for hit in hits][:k]