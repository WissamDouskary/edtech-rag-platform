import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    email: "",
    password: "",
    password2: "",
  });
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  function updateField(field) {
    return (e) => setForm((prev) => ({ ...prev, [field]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      await register(form);
      navigate("/", { replace: true });
    } catch (err) {
      const data = err.response?.data;
      const message = data
        ? Object.entries(data)
            .map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(", ") : msgs}`)
            .join(" | ")
        : "Registration failed. Please try again.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Create an account</h1>
        {error && <div className="error-banner">{error}</div>}
        <form onSubmit={handleSubmit}>
          <label>
            First name
            <input value={form.firstName} onChange={updateField("firstName")} />
          </label>
          <label>
            Last name
            <input value={form.lastName} onChange={updateField("lastName")} />
          </label>
          <label>
            Email
            <input type="email" value={form.email} onChange={updateField("email")} required />
          </label>
          <label>
            Password
            <input
              type="password"
              value={form.password}
              onChange={updateField("password")}
              minLength={8}
              required
            />
          </label>
          <label>
            Confirm password
            <input
              type="password"
              value={form.password2}
              onChange={updateField("password2")}
              minLength={8}
              required
            />
          </label>
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Creating account..." : "Create account"}
          </button>
        </form>
        <p className="auth-switch">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
