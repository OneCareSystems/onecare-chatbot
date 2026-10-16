import json
import logging
import os
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from django.conf import settings
from django.db import connection
from django.db.models import F

from .models import KnowledgeChunk, KnowledgeDocument

logger = logging.getLogger(__name__)
MANIFEST = "manifest.json"
_cache = {"version": None, "dir": None, "index": None}


class IndexBusy(RuntimeError):
    pass


class IndexInconsistent(RuntimeError):
    pass


def _root():
    return Path(settings.CHATBOT_STORAGE_DIR)


def index_dir():
    directory = _root() / "faiss"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def vectors_dir(doc_id):
    return _root() / "vectors" / str(doc_id)


def reset_cache():
    _cache.update(version=None, dir=None, index=None)


@contextmanager
def index_lock(timeout=60):
    """One index rebuild at a time (MySQL advisory lock, scoped to the chatbot database)."""
    name = f"onecare_kb_index:{settings.DATABASES['default']['NAME']}"
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, %s)", [name, timeout])
        if cursor.fetchone()[0] != 1:
            raise IndexBusy("The vector index is busy; try again.")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT RELEASE_LOCK(%s)", [name])


# ---- per-document vector files (one file per index_version) ----
def save_vectors(doc_id, version, array):
    directory = vectors_dir(doc_id)
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / f"v{version}.tmp.npy"
    np.save(tmp, np.asarray(array, dtype="float32"))
    os.replace(tmp, directory / f"v{version}.npy")


def load_vectors(doc_id, version):
    return np.load(vectors_dir(doc_id) / f"v{version}.npy")


def delete_vectors(doc_id, version=None):
    directory = vectors_dir(doc_id)
    if version is None:
        shutil.rmtree(directory, ignore_errors=True)
    else:
        (directory / f"v{version}.npy").unlink(missing_ok=True)


def delete_other_versions(doc_id, keep):
    for path in vectors_dir(doc_id).glob("v*.npy"):
        if path.name != f"v{keep}.npy":
            path.unlink(missing_ok=True)


# ---- the global FAISS index ----
def read_manifest():
    path = index_dir() / MANIFEST
    return json.loads(path.read_text()) if path.exists() else None


def _live_pairs(include):
    pairs = {}
    for doc_id, version in KnowledgeDocument.objects.filter(
            status=KnowledgeDocument.Status.INDEXED, active_version__gt=0).values_list("id", "active_version"):
        pairs.setdefault(doc_id, set()).add(version)
    for doc_id, version in include:                       # a new version that is staged but not yet active
        pairs.setdefault(doc_id, set()).add(version)
    return pairs


def build_index(include=()):
    """Rebuild the global index from INDEXED documents (plus `include`) and switch to it atomically.
    Call it while holding index_lock()."""
    import faiss
    chunk_ids, blocks = [], []
    for doc_id, versions in sorted(_live_pairs(include).items()):
        for version in sorted(versions):
            ids = list(KnowledgeChunk.objects.filter(document_id=doc_id, version=version)
                       .order_by("position").values_list("id", flat=True))
            if not ids:
                continue
            vectors = load_vectors(doc_id, version)
            if len(vectors) != len(ids):
                raise IndexInconsistent(f"Document {doc_id} v{version}: {len(ids)} chunks but {len(vectors)} vectors")
            chunk_ids += ids
            blocks.append(vectors)
    directory, old = index_dir(), read_manifest()
    number = (old["version"] if old else 0) + 1
    index_file = None
    if blocks:
        matrix = np.vstack(blocks).astype("float32")
        index = faiss.IndexFlatIP(matrix.shape[1])          # normalized vectors: inner product = cosine
        index.add(matrix)
        index_file = f"index_{number}.faiss"
        faiss.write_index(index, str(directory / (index_file + ".tmp")))
        os.replace(directory / (index_file + ".tmp"), directory / index_file)
    manifest = {"version": number, "index_file": index_file, "chunk_ids": chunk_ids,
                "built_at": datetime.now(timezone.utc).isoformat()}
    tmp = directory / (MANIFEST + ".tmp")
    tmp.write_text(json.dumps(manifest))
    os.replace(tmp, directory / MANIFEST)                   # <- the atomic switch
    for path in directory.glob("index_*.faiss"):
        if path.name != index_file:
            try:
                path.unlink()
            except OSError:
                logger.warning("Could not remove old index file %s", path.name)
    return manifest


def load_active_index():
    import faiss
    for _ in range(2):                                      # retry once if a rebuild swapped files under us
        manifest = read_manifest()
        if not manifest or not manifest["index_file"]:
            return manifest, None
        directory = index_dir()
        if _cache["version"] != manifest["version"] or _cache["dir"] != str(directory):
            try:
                index = faiss.read_index(str(directory / manifest["index_file"]))
            except (OSError, RuntimeError):
                continue
            _cache.update(version=manifest["version"], dir=str(directory), index=index)
        return manifest, _cache["index"]
    return None, None


def check_consistency():
    """live = chunks that queries may use. Every live chunk must be in the index. Extra vectors are harmless
    (queries filter them out) but are reported so you can rebuild."""
    manifest = read_manifest()
    indexed = set(manifest["chunk_ids"]) if manifest else set()
    live = set(KnowledgeChunk.objects.filter(
        document__status=KnowledgeDocument.Status.INDEXED, version=F("document__active_version"))
        .values_list("id", flat=True))
    return {"missing_from_index": sorted(live - indexed), "stale_in_index": sorted(indexed - live),
            "consistent": live <= indexed}