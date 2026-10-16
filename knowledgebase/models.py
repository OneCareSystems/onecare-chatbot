from django.db import models


class KnowledgeDocument(models.Model):
    CASE_SENSITIVE = "utf8mb4_0900_as_cs"

    class SourceType(models.TextChoices):
        PDF = "PDF"
        WEB = "WEB"

    class Status(models.TextChoices):
        PENDING = "PENDING"
        PROCESSING = "PROCESSING"
        INDEXED = "INDEXED"
        FAILED = "FAILED"
        REMOVED = "REMOVED"

    class Language(models.TextChoices):
        EN = "EN"
        TA = "TA"
        UNKNOWN = "UNKNOWN"

    title = models.CharField(max_length=255)
    source_type = models.CharField(max_length=16, choices=SourceType.choices, db_collation=CASE_SENSITIVE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING,
                              db_collation=CASE_SENSITIVE)
    language = models.CharField(max_length=8, choices=Language.choices, blank=True, default="",
                                db_collation=CASE_SENSITIVE)
    storage_path = models.CharField(max_length=500, blank=True, default="")
    content_sha256 = models.CharField(max_length=64, blank=True, default="")
    failure_reason = models.CharField(max_length=500, blank=True, default="")
    removed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    active_version = models.PositiveIntegerField(default=0)
    created_by_external_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    needs_review = models.BooleanField(default=False)
    original_filename = models.CharField(max_length=255, blank=True, default="")
    source_url = models.CharField(max_length=2048, null=True, blank=True)
    url_hash = models.CharField(max_length=64, null=True, blank=True, unique=True)

    class Meta:
        db_table = "knowledge_document"
        indexes = (models.Index(fields=["status"], name="ix_kd_status"),)
        constraints = (
            models.CheckConstraint(
                condition=models.Q(status__in=["PENDING", "PROCESSING", "INDEXED", "FAILED", "REMOVED"]),
                name="ck_knowledge_document_status",
            ),
            models.CheckConstraint(
                condition=models.Q(source_type__in=["PDF", "WEB"]),
                name="ck_knowledge_document_source_type",
            ),
            models.CheckConstraint(
                condition=models.Q(language__in=["", "EN", "TA", "UNKNOWN"]),
                name="ck_knowledge_document_language",
            ),
            models.CheckConstraint(
                condition=models.Q(source_type="PDF") | models.Q(source_url__isnull=False),
                name="ck_knowledge_document_web_has_url",
            ),
        )


class KnowledgeAuditEvent(models.Model):
    class Action(models.TextChoices):
        DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
        LINK_SUBMITTED = "LINK_SUBMITTED"
        DOCUMENT_REMOVED = "DOCUMENT_REMOVED"

    document = models.ForeignKey(
        KnowledgeDocument,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    resource = models.CharField(max_length=32, default="KNOWLEDGE_DOCUMENT")
    resource_id = models.CharField(max_length=64, blank=True, default="")
    actor_external_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    details = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "knowledge_audit_event"


class KnowledgeChunk(models.Model):
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name="chunks")
    version = models.PositiveIntegerField()
    position = models.PositiveIntegerField()
    text = models.TextField()
    token_count = models.PositiveIntegerField(default=0)
    language = models.CharField(max_length=8, blank=True, default="")
    source = models.CharField(max_length=2048, blank=True, default="")
    uploaded_by_external_id = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        db_table = "knowledge_chunk"
        indexes = (models.Index(fields=["document", "version"], name="ix_kc_doc_version"),)
        constraints = (
            models.UniqueConstraint(
                fields=("document", "version", "position"),
                name="uq_kc_doc_version_pos",
            ),
        )
