import hashlib
import itertools

from knowledgebase.repositories import KnowledgeDocumentRepository

_n = itertools.count(1)


def make_document(**overrides):
    n = next(_n)
    data = {
        "file_name": f"clinic_guide_{n}.pdf",
        "storage_path": f"kb_pdfs/clinic_guide_{n}.pdf",
        "content_hash": hashlib.sha256(f"file-{n}".encode()).hexdigest(),
        "uploaded_by": 42,                      # user ID supplied by Spring Boot
    }
    data.update(overrides)
    return KnowledgeDocumentRepository().create(**data)


RAW_INSERT = (
    "INSERT INTO knowledge_document "
    "(file_name, source_type, storage_path, content_hash, status, uploaded_by, uploaded_at, updated_at) "
    "VALUES ('raw.pdf', %s, 'kb_pdfs/raw.pdf', REPEAT('a', 64), %s, 1, NOW(6), NOW(6))"
)