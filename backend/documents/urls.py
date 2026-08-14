from django.urls import path

from .views import (
    DocumentConfirmView,
    DocumentDetailView,
    DocumentDownloadURLView,
    DocumentListView,
    DocumentRetryView,
    DocumentUploadURLView,
)

urlpatterns = [
    path("upload-url/", DocumentUploadURLView.as_view(), name="document-upload-url"),
    path("confirm/", DocumentConfirmView.as_view(), name="document-confirm"),
    path("", DocumentListView.as_view(), name="document-list"),
    path("<int:pk>/", DocumentDetailView.as_view(), name="document-detail"),
    path("<int:pk>/retry/", DocumentRetryView.as_view(), name="document-retry"),
    path("<int:pk>/download-url/", DocumentDownloadURLView.as_view(), name="document-download-url"),
]
