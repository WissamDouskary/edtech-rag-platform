import apiClient from "./client";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export async function listConversations() {
  const { data } = await apiClient.get("/rag/conversations/");
  return data;
}

export async function getConversation(id) {
  const { data } = await apiClient.get(`/rag/conversations/${id}/`);
  return data;
}

export async function createConversation({ scope, documentIds, vulgarizationLevel }) {
  const { data } = await apiClient.post("/rag/conversations/", {
    scope,
    document_ids: documentIds || [],
    vulgarization_level: vulgarizationLevel,
  });
  return data;
}

export async function deleteConversation(id) {
  await apiClient.delete(`/rag/conversations/${id}/`);
}

/**
 * Sends a message and streams the assistant's response via SSE.
 * Uses fetch (not EventSource) so we can attach the JWT Authorization header.
 * callbacks: { onIntent, onToken, onDone, onError }
 */
export async function sendMessageStream(conversationId, content, callbacks = {}) {
  const accessToken = localStorage.getItem("access_token");
  const response = await fetch(
    `${API_BASE_URL}/rag/conversations/${conversationId}/messages/`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ content }),
    }
  );

  if (!response.ok || !response.body) {
    const text = await response.text().catch(() => "");
    throw new Error(text || `Erreur HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop();

    for (const rawEvent of events) {
      const lines = rawEvent.split("\n");
      let eventType = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) eventType = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      const parsed = JSON.parse(data);
      if (eventType === "intent") callbacks.onIntent?.(parsed);
      else if (eventType === "token") callbacks.onToken?.(parsed.delta);
      else if (eventType === "done") callbacks.onDone?.(parsed);
      else if (eventType === "error") callbacks.onError?.(parsed);
    }
  }
}
