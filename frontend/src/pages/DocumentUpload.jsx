import { useRef, useState } from "react";
import { uploadDocument } from "../api/documents";

const MAX_SIZE_BYTES = 50 * 1024 * 1024;

export default function DocumentUpload({ onUploaded }) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");

  async function handleFile(file) {
    setError("");

    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Seuls les fichiers PDF sont acceptés.");
      return;
    }
    if (file.size > MAX_SIZE_BYTES) {
      setError("Le fichier dépasse la taille maximale autorisée (50 Mo).");
      return;
    }

    setIsUploading(true);
    setProgress(0);
    try {
      const document = await uploadDocument(file, setProgress);
      onUploaded?.(document);
    } catch (err) {
      setError(err.response?.data?.detail || "Échec du téléversement. Réessayez.");
    } finally {
      setIsUploading(false);
      setProgress(0);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    handleFile(file);
  }

  return (
    <div>
      <div
        className={`upload-dropzone${isDragging ? " dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        {isUploading ? (
          <span>Téléversement en cours... {progress}%</span>
        ) : (
          <span>Glissez-déposez un PDF ici, ou cliquez pour en choisir un (≤ 50 Mo)</span>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          hidden
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
      </div>
      {error && <div className="error-banner" style={{ marginTop: "0.75rem" }}>{error}</div>}
    </div>
  );
}
