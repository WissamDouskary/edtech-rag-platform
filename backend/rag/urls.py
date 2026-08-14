from django.urls import path

from .views import ConversationDetailView, ConversationListCreateView, ConversationMessageView

urlpatterns = [
    path("conversations/", ConversationListCreateView.as_view(), name="conversation-list"),
    path("conversations/<int:pk>/", ConversationDetailView.as_view(), name="conversation-detail"),
    path(
        "conversations/<int:pk>/messages/",
        ConversationMessageView.as_view(),
        name="conversation-messages",
    ),
]
