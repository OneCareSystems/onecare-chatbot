from dataclasses import dataclass

from .repositories import KnowledgeDocumentRepository
from .vector_index import VectorIndexRebuilder


@dataclass(frozen=True)
class VectorRebuildResult:
    documents_seen: int


def rebuild_vector_index(
    repository: KnowledgeDocumentRepository,
    rebuilder: VectorIndexRebuilder,
) -> VectorRebuildResult:
    document_ids = [document.pk for document in repository.list_indexable()]
    rebuilder.rebuild(document_ids)
    return VectorRebuildResult(documents_seen=len(document_ids))
