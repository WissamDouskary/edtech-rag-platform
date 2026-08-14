from rest_framework import serializers

from documents.models import Document

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "intent", "citations", "created_at"]
        read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
    document_ids = serializers.PrimaryKeyRelatedField(
        source="documents", many=True, queryset=Document.objects.none(), required=False
    )

    class Meta:
        model = Conversation
        fields = [
            "id",
            "title",
            "scope",
            "document_ids",
            "vulgarization_level",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None:
            self.fields["document_ids"].child_relation.queryset = Document.objects.filter(
                owner=request.user, status=Document.Status.READY
            )

    def validate(self, attrs):
        scope = attrs.get("scope", getattr(self.instance, "scope", None))
        documents = attrs.get("documents", [])
        if scope == Conversation.Scope.DOCUMENT and len(documents) != 1:
            raise serializers.ValidationError(
                {"document_ids": "Le périmètre 'document unique' exige exactement un document."}
            )
        if scope == Conversation.Scope.DOCUMENTS and len(documents) < 1:
            raise serializers.ValidationError(
                {"document_ids": "Sélectionnez au moins un document."}
            )
        if scope == Conversation.Scope.WORKSPACE:
            attrs["documents"] = []
        return attrs


class ConversationDetailSerializer(ConversationSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ["messages"]


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=4000)
