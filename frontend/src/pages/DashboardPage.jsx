import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import DocumentList from "./DocumentList.jsx";
import DocumentUpload from "./DocumentUpload.jsx";

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const [refreshToken, setRefreshToken] = useState(0);

  return (
    <div className="app-shell">
      <div className="topbar">
        <strong>EdTech RAG Platform</strong>
        <div>
          <Link to="/chat" style={{ marginRight: "1rem" }}>
            Discuter avec mes documents
          </Link>
          <span style={{ marginRight: "1rem" }}>
            {user?.email} ({user?.role})
          </span>
          <button onClick={logout}>Log out</button>
        </div>
      </div>
      <div className="dashboard">
        <h2>Mes documents</h2>
        <DocumentUpload onUploaded={() => setRefreshToken((t) => t + 1)} />
        <div style={{ marginTop: "1.5rem" }}>
          <DocumentList refreshToken={refreshToken} />
        </div>
      </div>
    </div>
  );
}
