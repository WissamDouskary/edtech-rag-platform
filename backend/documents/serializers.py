from rest_framework import serializers

from .constants import ALLOWED_CONTENT_TYPE, MAX_UPLOAD_SIZE_BYTES
from .models import Document


def _validate_pdf_filename(value):
    if not value.lower().endswith(".pdf"):
        raise serializers.ValidationError("Seuls les fichiers PDF sont acceptés.")
    return value


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "filename",
            "status",
            "size_bytes",
            "page_count",
            "failure_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "size_bytes",
            "page_count",
            "failure_reason",
            "created_at",
            "updated_at",
        ]

    def validate_filename(self, value):
        return _validate_pdf_filename(value)


class UploadURLRequestSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100)
    size_bytes = serializers.IntegerField()

    def validate_filename(self, value):
        return _validate_pdf_filename(value)

    def validate_content_type(self, value):
        if value != ALLOWED_CONTENT_TYPE:
            raise serializers.ValidationError(
                f"Type de fichier invalide, seul {ALLOWED_CONTENT_TYPE} est accepté."
            )
        return value

    def validate_size_bytes(self, value):
        if value <= 0:
            raise serializers.ValidationError("Taille de fichier invalide.")
        if value > MAX_UPLOAD_SIZE_BYTES:
            raise serializers.ValidationError(
                "Le fichier dépasse la taille maximale autorisée (50 Mo)."
            )
        return value


class ConfirmUploadSerializer(serializers.Serializer):
    storage_key = serializers.CharField(max_length=512)
    filename = serializers.CharField(max_length=255)

    def validate_filename(self, value):
        return _validate_pdf_filename(value)
