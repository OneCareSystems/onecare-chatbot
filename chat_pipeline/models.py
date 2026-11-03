from typing import ClassVar

from django.db import models
from django.utils import timezone


class ChatLog(models.Model):
    """CHAT-10: one row per patient query, for audit and later evaluation. Patients are anonymous: no user id, no IP.
    The text is redacted (e-mail, phone, ID numbers) and truncated before it is stored."""
    id = models.BigAutoField(primary_key=True)
    request_id = models.CharField(max_length=32, unique=True)              # also returned to the caller as requestId
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    query_text = models.TextField()
    response_text = models.TextField()
    response_type = models.CharField(max_length=16)                        # ANSWER | REFUSAL | FALLBACK | CLINIC_FACT
    detected_language = models.CharField(max_length=2)                     # EN | TA
    language_reason = models.CharField(max_length=64, blank=True)
    fallback_path = models.CharField(max_length=40, null=True, blank=True, db_index=True)   # null = no fallback happened
    guardrail_category = models.CharField(max_length=32, null=True, blank=True)
    best_score = models.FloatField(null=True, blank=True)
    matched_chunks = models.JSONField(default=list)                        # ids, source, score, used. Never chunk text
    llm_model = models.CharField(max_length=80, blank=True)
    prompt_version = models.CharField(max_length=16, blank=True)
    latency_ms = models.IntegerField(default=0)

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["response_type", "created_at"])]

    def __str__(self):
        return f"{self.request_id} {self.response_type} {self.fallback_path or '-'}"
