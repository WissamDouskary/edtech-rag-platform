from django.contrib import admin

from .models import Document, DocumentChunk


class DocumentChunkInline(admin.TabularInline):
    model = DocumentChunk
    extra = 0
    readonly_fields = ("chunk_index", "page_number", "char_count", "vector_id")
    can_delete = False


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("filename", "owner", "status", "size_bytes", "page_count", "created_at")
    list_filter = ("status",)
    search_fields = ("filename", "owner__email")
    readonly_fields = ("content_hash", "storage_key", "created_at", "updated_at")
    inlines = [DocumentChunkInline]
