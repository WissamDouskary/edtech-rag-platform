from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("role", "content", "intent", "citations", "created_at")
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "scope", "vulgarization_level", "updated_at")
    list_filter = ("scope", "vulgarization_level")
    search_fields = ("title", "owner__email")
    inlines = [MessageInline]
