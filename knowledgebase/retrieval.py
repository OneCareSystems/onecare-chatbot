import numpy as np
from django.db.models import F

from . import vector_index
from .embedding import get_embedder
from .models import KnowledgeChunk, KnowledgeDocument


def search(query, k=5):
    """Only chunks of INDEXED documents at their ACTIVE version are ever returned (defence in depth)."""
    manifest, index = vector_index.load_active_index()
    if index is None or index.ntotal == 0:
        return []
    query_vector = np.asarray(get_embedder().embed_query(query), dtype="float32").reshape(1, -1)
    scores, positions = index.search(query_vector, min(k * 4, index.ntotal))   # over-fetch, some hits get filtered
    ranked = {manifest["chunk_ids"][p]: float(s) for s, p in zip(scores[0], positions[0]) if p >= 0}
    rows = (KnowledgeChunk.objects.filter(id__in=ranked, document__status=KnowledgeDocument.Status.INDEXED,
                                          version=F("document__active_version")).select_related("document"))
    hits = [{"chunk_id": c.id, "document_id": c.document_id, "text": c.text, "language": c.language,
             "source": c.source, "score": ranked[c.id]} for c in rows]
    return sorted(hits, key=lambda h: -h["score"])[:k]