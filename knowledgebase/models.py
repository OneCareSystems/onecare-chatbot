from django.db import models

from .constants import CASE_SENSITIVE_COLLATION, DocumentStatus, Language, SourceType


def _check(condition, name):
    try:
        return models.CheckConstraint(condition=condition, name=name)
    except TypeError:
        return models.CheckConstraint(check=condition, name=name)


class KnowledgeDocument(models.Model):
    file_name = models.CharField(max_length=255)
    source_type = models.CharField(
        max_length=10,
        choices=SourceType.choices,
        default=SourceType.PDF,
        db_collation=CASE_SENSITIVE_COLLATION,
    )
    language = models.CharField(
        max_length=5,
        choices=Language.choices,
        null=True,
        blank=True,
        db_collation=CASE_SENSITIVE_COLLATION,
    )
    storage_path = models.CharField(max_length=500)
    content_hash = models.CharField(
        max_length=64,
        validators=[RegexValidator(r"^[0-9a-f]{64}$", "Enter a lowercase SHA-256 hash.")],
    )
    status = models.CharField(
        max_length=10,
        choices=DocumentStatus.choices,
        default=DocumentStatus.PENDING,
        db_collation=CASE_SENSITIVE_COLLATION,
    )
    failure_reason = models.CharField(max_length=500, null=True, blank=True)
    uploaded_by = models.PositiveBigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "knowledge_document"
        constraints = (
            _check(
                models.Q(status__in=DocumentStatus.values),
                "chk_knowledge_document_status",
            ),
            _check(
                models.Q(source_type=SourceType.PDF),
                "chk_knowledge_document_source_type",
            ),
            _check(
                models.Q(language__isnull=True) | models.Q(language__in=Language.values),
                "chk_knowledge_document_language",
            ),
        )
        indexes = (models.Index(fields=["status"], name="ix_kd_status"),)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.file_name} [{self.status}]"
