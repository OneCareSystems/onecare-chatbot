"""AC4: metadata is independent of vector storage."""
import pytest

from knowledgebase.models import KnowledgeDocument
from knowledgebase.repositories import KnowledgeDocumentRepository
from knowledgebase.services import rebuild_vector_index
from knowledgebase.vector_index import StubVectorIndexRebuilder, VectorIndexRebuilder
from tests.factories import make_document

pytestmark = [pytest.mark.mysql, pytest.mark.django_db]


def snapshot():
    return list(KnowledgeDocument.objects.order_by("id").values())      # every column, incl. updated_at


def test_stub_rebuild_does_not_modify_delete_or_duplicate_records():
    docs = [make_document(), make_document(), make_document(language="ta")]
    repo = KnowledgeDocumentRepository()
    repo.change_status(docs[1].pk, "INDEXED")
    repo.mark_removed(docs[2].pk)
    before = snapshot()

    stub = StubVectorIndexRebuilder()
    result = rebuild_vector_index(repo, stub)
    rebuild_vector_index(repo, stub)                                    # twice, to catch duplication

    assert snapshot() == before                                         # identical rows, identical timestamps
    assert KnowledgeDocument.objects.count() == 3
    assert result.documents_seen == 2                                   # REMOVED one excluded
    assert stub.calls[0] == [docs[0].pk, docs[1].pk]


def test_rebuild_with_no_documents_is_fine():
    result = rebuild_vector_index(KnowledgeDocumentRepository(), StubVectorIndexRebuilder())
    assert result.documents_seen == 0


def test_interface_is_abstract():
    with pytest.raises(TypeError):
        VectorIndexRebuilder()


def test_model_has_no_relations_or_vector_fields():
    fields = KnowledgeDocument._meta.get_fields()
    assert not [f.name for f in fields if f.is_relation]                # no FKs, no reverse relations, no cascades
    assert not [f.name for f in fields if any(w in f.name for w in ("vector", "embedding", "faiss"))]