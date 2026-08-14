import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { deleteDocument, listDocuments, renameDocument, retryDocument } from "../api/documents";

const STATUS_LABELS = {
  UPLOADED: "Téléversé",
  PROCESSING: "Traitement en cours",
  READY: "Prêt",
  FAILED: "Échec",
};

const ACTIVE_STATUSES = new Set(["UPLOADED", "PROCESSING"]);

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

export default function DocumentList({ refreshToken }) {
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const pollRef = useRef(null);

  async function refresh() {
    try {
      const data = await listDocuments();
      setDocuments(data);
      setError("");
    } catch (err) {
      setError("Impossible de charger les documents.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [refreshToken]);

  useEffect(() => {
    const hasActive = documents.some((d) => ACTIVE_STATUSES.has(d.status));
    if (hasActive) {
      pollRef.current = setInterval(refresh, 3000);
      return () => clearInterval(pollRef.current);
    }
    return undefined;
  }, [documents]);

  async function handleDelete(id) {
    if (!window.confirm("Supprimer ce document ? Cette action est irréversible.")) return;
    await deleteDocument(id);
    refresh();
  }

  async function handleRetry(id) {
    await retryDocument(id);
    refresh();
  }

  function startRename(doc) {
    setRenamingId(doc.id);
    setRenameValue(doc.filename);
  }

  async function submitRename(id) {
    if (renameValue.trim()) {
      await renameDocument(id, renameValue.trim());
    }
    setRenamingId(null);
    refresh();
  }

  if (isLoading) return <p>Chargement des documents...</p>;
  if (error) return <div className="error-banner">{error}</div>;
  if (documents.length === 0) return <p>Aucun document pour le moment.</p>;

  return (
    <table className="document-table">
      <thead>
        <tr>
          <th>Nom</th>
          <th>Statut</th>
          <th>Taille</th>
          <th>Pages</th>
          <th>Ajouté le</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {documents.map((doc) => (
          <tr key={doc.id}>
            <td>
              {renamingId === doc.id ? (
                <input
                  value={renameValue}
                  autoFocus
                  onChange={(e) => setRenameValue(e.target.value)}
                  onBlur={() => submitRename(doc.id)}
                  onKeyDown={(e) => e.key === "Enter" && submitRename(doc.id)}
                />
              ) : (
                <span onDoubleClick={() => startRename(doc)}>{doc.filename}</span>
              )}
            </td>
            <td>
              <span className={`status-badge status-${doc.status.toLowerCase()}`}>
                {STATUS_LABELS[doc.status] || doc.status}
              </span>
              {doc.status === "FAILED" && doc.failure_reason && (
                <div className="failure-reason">{doc.failure_reason}</div>
              )}
            </td>
            <td>{formatSize(doc.size_bytes)}</td>
            <td>{doc.page_count ?? "-"}</td>
            <td>{new Date(doc.created_at).toLocaleString()}</td>
            <td className="document-actions">
              {doc.status === "READY" && (
                <Link to={`/chat?doc=${doc.id}`}>
                  <button type="button">Discuter</button>
                </Link>
              )}
              <button onClick={() => startRename(doc)}>Renommer</button>
              {doc.status === "FAILED" && (
                <button onClick={() => handleRetry(doc.id)}>Relancer</button>
              )}
              <button onClick={() => handleDelete(doc.id)}>Supprimer</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
