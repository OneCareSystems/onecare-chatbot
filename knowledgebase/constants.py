"""Single source of truth for allowed values. Used by the model, the CHECK constraints,
the validators and the repository, so they can never drift apart."""
from django.db import models


class DocumentStatus(models.TextChoices):
    PENDING = "PENDING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"
    REMOVED = "REMOVED"


class SourceType(models.TextChoices):
    PDF = "PDF"


class Language(models.TextChoices):
    ENGLISH = "en"
    TAMIL = "ta"


# Statuses whose documents belong in the vector index. FAILED and REMOVED are excluded.
INDEXABLE_STATUSES = (DocumentStatus.PENDING, DocumentStatus.INDEXED)

CASE_SENSITIVE_COLLATION = "utf8mb4_0900_as_cs"