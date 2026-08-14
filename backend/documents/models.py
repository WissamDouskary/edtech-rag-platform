from django.conf import settings
from django.db import models


class Document(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "UPLOADED", "Uploaded"
        PROCESSING = "PROCESSING", "Processing"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents"
    )
    filename = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=512, unique=True)
    # MD5 ETag of the uploaded object (single-part PUT) — used to detect duplicate uploads.
    content_hash = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED)
    size_bytes = models.PositiveBigIntegerField()
    page_count = models.PositiveIntegerField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "content_hash"],
                condition=~models.Q(status="FAILED"),
                name="unique_owner_document_content",
            )
        ]

    def __str__(self):
        return f"{self.filename} ({self.owner_id})"


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.PositiveIntegerField()
    page_number = models.PositiveIntegerField()
    char_count = models.PositiveIntegerField()
    # id of the corresponding vector in the Chroma collection
    vector_id = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ["chunk_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "chunk_index"], name="unique_document_chunk_index"
            )
        ]

    def __str__(self):
        return f"{self.document_id}:{self.chunk_index}"
