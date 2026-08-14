import { useAuth } from "../context/AuthContext.jsx";

export default function DashboardPage() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <div className="topbar">
        <strong>EdTech RAG Platform</strong>
        <div>
          <span style={{ marginRight: "1rem" }}>
            {user?.email} ({user?.role})
          </span>
          <button onClick={logout}>Log out</button>
        </div>
      </div>
      <div className="dashboard">
        <h2>Welcome, {user?.first_name || user?.email}</h2>
        <p>Your workspace is empty. Document upload and RAG chat land in the next phase.</p>
      </div>
    </div>
  );
}
