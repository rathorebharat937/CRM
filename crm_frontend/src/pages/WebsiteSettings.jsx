import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";
import { SettingsStatusMessages } from "../utils/settingsPage";

function WebsiteSettings() {
  const role = localStorage.getItem("role") || "Staff";
  const [form, setForm] = useState({ company_slug: "", home_page_id: "", default_lead_assignee_id: "" });
  const [pages, setPages] = useState([]);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setError("");
    apiFetch("/website/settings").then((s) => {
      setForm({
        company_slug: s.company_slug,
        home_page_id: s.home_page_id || "",
        default_lead_assignee_id: s.default_lead_assignee_id || "",
      });
      setError("");
    }).catch((err) => setError(err.message));
    apiFetch("/website/pages").then((d) => setPages(d.items || [])).catch(() => {});
  }, []);

  const save = async () => {
    setError("");
    setSaved(false);
    try {
      await apiFetch("/website/settings", {
        method: "PUT",
        body: JSON.stringify({
          company_slug: form.company_slug,
          home_page_id: form.home_page_id ? Number(form.home_page_id) : null,
          default_lead_assignee_id: form.default_lead_assignee_id ? Number(form.default_lead_assignee_id) : null,
        }),
      });
      setError("");
      setSaved(true);
    } catch (err) {
      setSaved(false);
      setError(err.message);
    }
  };

  return (
    <DashboardLayout title="Website settings" roleLabel={role}>
      <div className="crm-panel">
        <Link to="/website" className="crm-back-link">← Website</Link>
        <SettingsStatusMessages error={error} saved={saved} />
        <div className="crm-form-grid crm-mt">
          <div className="crm-form-field">
            <label>Public company slug</label>
            <input value={form.company_slug} onChange={(e) => setForm({ ...form, company_slug: e.target.value })} />
            <p className="crm-muted">Public URL: /s/{form.company_slug || "your-slug"}</p>
          </div>
          <div className="crm-form-field">
            <label>Home page</label>
            <select value={form.home_page_id} onChange={(e) => setForm({ ...form, home_page_id: e.target.value })}>
              <option value="">Auto (first published)</option>
              {pages.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
            </select>
          </div>
        </div>
        <div className="crm-form-actions crm-mt">
          <button type="button" className="crm-btn" onClick={save}>Save settings</button>
        </div>
      </div>
    </DashboardLayout>
  );
}

export default WebsiteSettings;
