import shutil
import uuid
from pathlib import Path

from django.conf import settings


def root() -> Path:
    return Path(settings.CHATBOT_STORAGE_DIR).resolve()


def raw_dir(doc_id) -> Path:
    return root() / "documents" / str(doc_id)


def save_raw_pdf(doc_id, uploaded_file) -> str:
    """Returns the path relative to CHATBOT_STORAGE_DIR. (Swap this module for S3 in production if SDS 2.6.1 requires it.)"""
    directory = raw_dir(doc_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid.uuid4().hex}.pdf"
    with open(path, "wb") as handle:
        for chunk in uploaded_file.chunks():
            handle.write(chunk)
    return str(path.relative_to(root()))


def resolve(relative_path) -> Path:
    path = (root() / relative_path).resolve()
    if root() not in path.parents:
        raise ValueError("Path escapes the chatbot storage directory")
    return path


def delete_raw(doc_id):
    shutil.rmtree(raw_dir(doc_id), ignore_errors=True)