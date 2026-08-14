import uuid

from botocore.exceptions import ClientError
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .constants import ALLOWED_CONTENT_TYPE, MAX_UPLOAD_SIZE_BYTES
from .models import Document
from .serializers import ConfirmUploadSerializer, DocumentSerializer, UploadURLRequestSerializer
from .services.ingestion import delete_document_fully, ingest_document
from .services.quota import QuotaExceededError, check_quota
from .services.storage import delete_object, generate_download_url, generate_upload_url, head_object


class DocumentUploadURLView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UploadURLRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            check_quota(request.user, data["size_bytes"])
        except QuotaExceededError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        storage_key = f"documents/{request.user.id}/{uuid.uuid4().hex}.pdf"
        upload_url = generate_upload_url(storage_key, ALLOWED_CONTENT_TYPE)

        return Response(
            {
                "upload_url": upload_url,
                "storage_key": storage_key,
                "content_type": ALLOWED_CONTENT_TYPE,
                "expires_in": 600,
            }
        )


class DocumentConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ConfirmUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        storage_key = serializer.validated_data["storage_key"]
        filename = serializer.validated_data["filename"]

        if not storage_key.startswith(f"documents/{request.user.id}/"):
            return Response({"detail": "Clé de stockage invalide."}, status=status.HTTP_403_FORBIDDEN)

        try:
            head = head_object(storage_key)
        except ClientError:
            return Response(
                {"detail": "Fichier introuvable sur le stockage. Veuillez retélécharger."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        size_bytes = head["ContentLength"]
        if size_bytes > MAX_UPLOAD_SIZE_BYTES:
            delete_object(storage_key)
            return Response(
                {"detail": "Le fichier dépasse la taille maximale autorisée (50 Mo)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_hash = head["ETag"].strip('"')

        duplicate = (
            Document.objects.filter(owner=request.user, content_hash=content_hash)
            .exclude(status=Document.Status.FAILED)
            .exists()
        )
        if duplicate:
            delete_object(storage_key)
            return Response(
                {"detail": "Ce document a déjà été téléversé."}, status=status.HTTP_409_CONFLICT
            )

        try:
            check_quota(request.user, size_bytes)
        except QuotaExceededError as exc:
            delete_object(storage_key)
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        document = Document.objects.create(
            owner=request.user,
            filename=filename,
            storage_key=storage_key,
            content_hash=content_hash,
            size_bytes=size_bytes,
            status=Document.Status.UPLOADED,
        )

        ingest_document(document)
        document.refresh_from_db()

        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)


class DocumentListView(generics.ListAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user)


class DocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user)

    def perform_destroy(self, instance):
        delete_document_fully(instance)


class DocumentRetryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk, owner=request.user)
        if document.status != Document.Status.FAILED:
            return Response(
                {"detail": "Seuls les documents en échec peuvent être relancés."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ingest_document(document)
        document.refresh_from_db()
        return Response(DocumentSerializer(document).data)


class DocumentDownloadURLView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        document = get_object_or_404(Document, pk=pk, owner=request.user)
        if document.status != Document.Status.READY:
            return Response(
                {"detail": "Seuls les documents prêts peuvent être consultés."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        url = generate_download_url(document.storage_key, document.filename)
        return Response({"url": url, "expires_in": 600})
