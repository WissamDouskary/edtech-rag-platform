import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  sendMessageStream,
} from "../api/chat";
import { getDocumentDownloadUrl, listDocuments } from "../api/documents";
import { useAuth } from "../context/AuthContext.jsx";

const SCOPE_LABELS = {
  DOCUMENT: "Un document",
  DOCUMENTS: "Plusieurs documents",
  WORKSPACE: "Tout l'espace de travail",
};

const LEVEL_LABELS = {
  SIMPLE: "Simple",
  INTERMEDIATE: "Intermédiaire",
  EXPERT: "Expert",
};

const FOLLOW_UPS = [
  { label: "Approfondir", prompt: "Peux-tu approfondir ta réponse précédente ?" },
  { label: "Simplifier", prompt: "Peux-tu reformuler ta réponse précédente plus simplement ?" },
  { label: "Générer un quiz sur ce point", prompt: "Peux-tu me générer un quiz sur ce point ?" },
];

function renderContent(content, citations, onCiteClick) {
  const parts = content.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      const index = Number(match[1]);
      const citation = citations?.find((c) => c.index === index);
      if (citation) {
        return (
          <button key={i} className="citation-chip" onClick={() => onCiteClick(citation)}>
            [{index}]
          </button>
        );
      }
    }
    return <span key={i}>{part}</span>;
  });
}

export default function ChatPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const [conversations, setConversations] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [active, setActive] = useState(null);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newScope, setNewScope] = useState("WORKSPACE");
  const [newDocumentIds, setNewDocumentIds] = useState([]);
  const [newLevel, setNewLevel] = useState("INTERMEDIATE");
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [error, setError] = useState("");
  const [openCitation, setOpenCitation] = useState(null);
  const bottomRef = useRef(null);
  // Mirrors streamingText so the onDone SSE callback (created once per send) can
  // read the latest streamed value without becoming stale inside its closure.
  const streamingTextRef = useRef("");

  const readyDocuments = documents.filter((d) => d.status === "READY");

  async function refreshConversations() {
    const data = await listConversations();
    setConversations(data);
  }

  useEffect(() => {
    refreshConversations();
    listDocuments().then(setDocuments).catch(() => {});
  }, []);

  useEffect(() => {
    const preselectDoc = searchParams.get("doc");
    if (preselectDoc) {
      setShowNewForm(true);
      setNewScope("DOCUMENT");
      setNewDocumentIds([Number(preselectDoc)]);
    }
  }, [searchParams]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [active, streamingText]);

  async function openConversation(id) {
    const data = await getConversation(id);
    setActive(data);
    setShowNewForm(false);
  }

  async function handleCreateConversation(e) {
    e.preventDefault();
    setError("");
    try {
      const conv = await createConversation({
        scope: newScope,
        documentIds: newScope === "WORKSPACE" ? [] : newDocumentIds,
        vulgarizationLevel: newLevel,
      });
      await refreshConversations();
      setActive({ ...conv, messages: [] });
      setShowNewForm(false);
    } catch (err) {
      setError(err.response?.data?.document_ids?.[0] || "Impossible de créer la conversation.");
    }
  }

  async function handleDeleteConversation(id) {
    if (!window.confirm("Supprimer cette conversation ?")) return;
    await deleteConversation(id);
    if (active?.id === id) setActive(null);
    refreshConversations();
  }

  async function handleSend(content) {
    if (!content.trim() || !active || isStreaming) return;
    setError("");
    setInput("");
    const userMessage = { id: `local-${Date.now()}`, role: "USER", content, citations: [] };
    setActive((prev) => ({ ...prev, messages: [...prev.messages, userMessage] }));
    setIsStreaming(true);
    setStreamingText("");

    try {
      await sendMessageStream(active.id, content, {
        onToken: (delta) => setStreamingText((prev) => prev + delta),
        onDone: ({ message_id: messageId, citations, intent }) => {
          setActive((prev) => ({
            ...prev,
            messages: [
              ...prev.messages,
              { id: messageId, role: "ASSISTANT", content: streamingTextRef.current, citations, intent },
            ],
          }));
          setStreamingText("");
          setIsStreaming(false);
        },
        onError: (err) => {
          setError(err.detail || "Erreur lors de la génération de la réponse.");
          setIsStreaming(false);
        },
      });
    } catch (err) {
      setError(err.message || "Erreur réseau.");
      setIsStreaming(false);
    }
  }

  useEffect(() => {
    streamingTextRef.current = streamingText;
  }, [streamingText]);

  async function handleCitationClick(citation) {
    setOpenCitation((prev) => (prev?.chunk_id === citation.chunk_id ? null : citation));
  }

  async function openPdfAtPage(citation) {
    const { url } = await getDocumentDownloadUrl(citation.document_id);
    window.open(`${url}#page=${citation.page_number}`, "_blank");
  }

  return (
    <div className="app-shell">
      <div className="topbar">
        <strong>EdTech RAG Platform</strong>
        <div>
          <Link to="/" style={{ marginRight: "1rem" }}>
            Mes documents
          </Link>
          <span>{user?.email}</span>
        </div>
      </div>

      <div className="chat-layout">
        <aside className="chat-sidebar">
          <button className="new-conversation-btn" onClick={() => setShowNewForm(true)}>
            + Nouvelle conversation
          </button>
          <ul className="conversation-list">
            {conversations.map((c) => (
              <li key={c.id} className={active?.id === c.id ? "active" : ""}>
                <button onClick={() => openConversation(c.id)}>
                  <span className="conv-title">{c.title || "Nouvelle conversation"}</span>
                  <span className="conv-scope">{SCOPE_LABELS[c.scope]}</span>
                </button>
                <button className="conv-delete" onClick={() => handleDeleteConversation(c.id)}>
                  ×
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <main className="chat-main">
          {showNewForm && (
            <form className="new-conversation-form" onSubmit={handleCreateConversation}>
              <h3>Nouvelle conversation</h3>
              <label>
                Périmètre
                <select value={newScope} onChange={(e) => setNewScope(e.target.value)}>
                  <option value="WORKSPACE">Tout l'espace de travail</option>
                  <option value="DOCUMENT">Un document</option>
                  <option value="DOCUMENTS">Plusieurs documents</option>
                </select>
              </label>

              {(newScope === "DOCUMENT" || newScope === "DOCUMENTS") && (
                <label>
                  Documents ({readyDocuments.length} prêt(s))
                  <select
                    multiple={newScope === "DOCUMENTS"}
                    value={newScope === "DOCUMENTS" ? newDocumentIds.map(String) : String(newDocumentIds[0] || "")}
                    onChange={(e) => {
                      const values = Array.from(e.target.selectedOptions, (o) => Number(o.value));
                      setNewDocumentIds(newScope === "DOCUMENTS" ? values : [values[0]]);
                    }}
                  >
                    {newScope === "DOCUMENT" && <option value="">-- choisir --</option>}
                    {readyDocuments.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.filename}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              <label>
                Niveau de vulgarisation
                <select value={newLevel} onChange={(e) => setNewLevel(e.target.value)}>
                  {Object.entries(LEVEL_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>

              {error && <div className="error-banner">{error}</div>}

              <div>
                <button type="submit">Créer</button>
                <button type="button" onClick={() => setShowNewForm(false)}>
                  Annuler
                </button>
              </div>
            </form>
          )}

          {!showNewForm && !active && <p>Sélectionnez ou créez une conversation.</p>}

          {!showNewForm && active && (
            <>
              <div className="chat-meta">
                <span className="status-badge status-ready">{SCOPE_LABELS[active.scope]}</span>
                <span className="status-badge status-uploaded">
                  {LEVEL_LABELS[active.vulgarization_level]}
                </span>
              </div>

              <div className="chat-messages">
                {active.messages.map((m) => (
                  <div key={m.id} className={`chat-bubble chat-${m.role.toLowerCase()}`}>
                    <div className="chat-bubble-content">
                      {renderContent(m.content, m.citations, handleCitationClick)}
                    </div>
                    {m.citations?.length > 0 && (
                      <div className="citation-list">
                        {m.citations.map((c) => (
                          <div key={c.index} className="citation-item">
                            <button className="citation-chip" onClick={() => handleCitationClick(c)}>
                              [{c.index}] {c.document_filename} — p.{c.page_number}
                            </button>
                            {openCitation?.chunk_id === c.chunk_id && (
                              <div className="citation-excerpt">
                                <p>{c.excerpt}</p>
                                <button onClick={() => openPdfAtPage(c)}>
                                  Ouvrir le PDF à la page {c.page_number}
                                </button>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    {m.role === "ASSISTANT" && !isStreaming && (
                      <div className="follow-up-actions">
                        {FOLLOW_UPS.map((f) => (
                          <button key={f.label} onClick={() => handleSend(f.prompt)}>
                            {f.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}

                {isStreaming && (
                  <div className="chat-bubble chat-assistant">
                    <div className="chat-bubble-content">
                      {streamingText || "..."}
                    </div>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>

              {error && <div className="error-banner">{error}</div>}

              <form
                className="chat-input-row"
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSend(input);
                }}
              >
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Posez votre question..."
                  disabled={isStreaming}
                />
                <button type="submit" disabled={isStreaming || !input.trim()}>
                  Envoyer
                </button>
              </form>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
