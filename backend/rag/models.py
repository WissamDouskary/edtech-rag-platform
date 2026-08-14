from django.conf import settings
from django.db import models


class Conversation(models.Model):
    class Scope(models.TextChoices):
        DOCUMENT = "DOCUMENT", "Document unique"
        DOCUMENTS = "DOCUMENTS", "Plusieurs documents"
        WORKSPACE = "WORKSPACE", "Tout l'espace de travail"

    class VulgarizationLevel(models.TextChoices):
        SIMPLE = "SIMPLE", "Simple"
        INTERMEDIATE = "INTERMEDIATE", "Intermédiaire"
        EXPERT = "EXPERT", "Expert"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations"
    )
    title = models.CharField(max_length=255, blank=True)
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.WORKSPACE)
    documents = models.ManyToManyField(
        "documents.Document", blank=True, related_name="conversations"
    )
    vulgarization_level = models.CharField(
        max_length=20,
        choices=VulgarizationLevel.choices,
        default=VulgarizationLevel.INTERMEDIATE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Conversation {self.id}"


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "USER", "user"
        ASSISTANT = "ASSISTANT", "assistant"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    intent = models.CharField(max_length=30, blank=True)
    # list of {index, document_id, document_filename, page_number, chunk_id, excerpt}
    citations = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.conversation_id}:{self.role}:{self.id}"
