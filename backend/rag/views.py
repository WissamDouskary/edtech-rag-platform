import json
import logging

from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from documents.models import Document, DocumentChunk

from .models import Conversation, Message
from .serializers import ConversationDetailSerializer, ConversationSerializer, SendMessageSerializer
from .services.agents import agent_pedagogique, agent_rag, orchestrateur
from .services.citations import extract_citations

logger = logging.getLogger(__name__)


def _format_sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class ConversationListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(owner=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ConversationDetailView(generics.RetrieveDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ConversationDetailSerializer

    def get_queryset(self):
        return Conversation.objects.filter(owner=self.request.user).prefetch_related(
            "messages", "documents"
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


def _build_enriched_chunks(chunks):
    """Attach document filename + DocumentChunk pk to each retrieved chunk."""
    if not chunks:
        return []

    documents = Document.objects.in_bulk({c["document_id"] for c in chunks})
    chunk_pks = DocumentChunk.objects.filter(
        vector_id__in=[c["vector_id"] for c in chunks]
    ).values_list("vector_id", "id")
    chunk_pk_by_vector_id = dict(chunk_pks)

    enriched = []
    for chunk in chunks:
        doc = documents.get(chunk["document_id"])
        enriched.append(
            {
                **chunk,
                "document_filename": doc.filename if doc else None,
                "chunk_id": chunk_pk_by_vector_id.get(chunk["vector_id"]),
            }
        )
    return enriched


class ConversationMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        conversation = get_object_or_404(
            Conversation.objects.prefetch_related("documents"), pk=pk, owner=request.user
        )
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_content = serializer.validated_data["content"]

        history = list(
            conversation.messages.order_by("created_at").values("role", "content")
        )

        Message.objects.create(conversation=conversation, role=Message.Role.USER, content=user_content)
        if not conversation.title:
            conversation.title = user_content[:60]
            conversation.save(update_fields=["title", "updated_at"])

        if conversation.scope == Conversation.Scope.WORKSPACE:
            document_ids = None
        else:
            document_ids = list(conversation.documents.values_list("id", flat=True))

        level = conversation.vulgarization_level
        owner_id = request.user.id

        def event_stream():
            try:
                classification = orchestrateur.run(history, user_content)
                intent = classification["intent"]
                enriched_query = classification["enriched_query"]
                yield _format_sse("intent", {"intent": intent, "enriched_query": enriched_query})

                chunks = agent_rag.run(owner_id, document_ids, enriched_query)
                enriched_chunks = _build_enriched_chunks(chunks)

                full_text = ""
                for delta in agent_pedagogique.run(history, chunks, enriched_query, intent, level):
                    full_text += delta
                    yield _format_sse("token", {"delta": delta})

                citations = extract_citations(full_text, enriched_chunks)

                assistant_message = Message.objects.create(
                    conversation=conversation,
                    role=Message.Role.ASSISTANT,
                    content=full_text,
                    intent=intent,
                    citations=citations,
                )
                conversation.save(update_fields=["updated_at"])

                yield _format_sse(
                    "done",
                    {
                        "message_id": assistant_message.id,
                        "citations": citations,
                        "intent": intent,
                    },
                )
            except Exception:
                logger.exception("Chat streaming failed for conversation %s", conversation.id)
                yield _format_sse(
                    "error", {"detail": "Une erreur est survenue lors de la génération de la réponse."}
                )

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
