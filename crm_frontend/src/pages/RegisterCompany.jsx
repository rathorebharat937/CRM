import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { API_URL, saveSession } from "../utils/api";

function RegisterCompany() {
  const navigate = useNavigate();
  const [ownerName, setOwnerName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [password, setPassword] = useState("");
  const [legalName, setLegalName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/register-company`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          owner_name: ownerName,
          owner_email: ownerEmail,
          password,
          company_legal_name: legalName,
          company_display_name: displayName || legalName,
          phone: phone || null,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        setError(data.detail || "Registration failed");
        return;
      }

      saveSession(data);
      localStorage.setItem("company_id", String(data.company_id));
      localStorage.setItem("company_name", data.company_name);
      localStorage.removeItem("onboarding_complete");
      navigate("/onboarding");
    } catch {
      setError("Cannot reach the server. Make sure the backend is running on port 8000.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="crm-card crm-card-wide">
      <h2>Register your business</h2>
      <p className="crm-muted crm-mb">
        Create your company workspace and become the Admin. You can invite staff and
        configure GST billing after signup.
      </p>

      <form onSubmit={handleSubmit} className="crm-form">
        <h3 className="crm-section-title">Your account</h3>
        <label htmlFor="owner-name">Your name</label>
        <input
          id="owner-name"
          type="text"
          value={ownerName}
          onChange={(e) => setOwnerName(e.target.value)}
          required
        />

        <label htmlFor="owner-email">Work email</label>
        <input
          id="owner-email"
          type="email"
          value={ownerEmail}
          onChange={(e) => setOwnerEmail(e.target.value)}
          required
        />

        <label htmlFor="owner-password">Password</label>
        <input
          id="owner-password"
          type="password"
          minLength={6}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        <label htmlFor="owner-phone">Phone (optional)</label>
        <input
          id="owner-phone"
          type="tel"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />

        <h3 className="crm-section-title crm-mt">Company details</h3>
        <label htmlFor="legal-name">Legal / registered name</label>
        <input
          id="legal-name"
          type="text"
          value={legalName}
          onChange={(e) => setLegalName(e.target.value)}
          required
        />

        <label htmlFor="display-name">Display name (optional)</label>
        <input
          id="display-name"
          type="text"
          placeholder="Shown on invoices and dashboard"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />

        {error && <p className="crm-error">{error}</p>}

        <button type="submit" className="crm-btn crm-btn-primary" disabled={loading}>
          {loading ? "Creating workspace…" : "Create workspace"}
        </button>
      </form>

      <p className="crm-auth-switch">
        Already have an account?{" "}
        <Link to="/admin-login">Staff sign in</Link>
      </p>

      <Link to="/" className="crm-link">
        Back to home
      </Link>
    </div>
  );
}

export default RegisterCompany;
