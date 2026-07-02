import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { DOMAIN_LABELS, PERIOD_LABELS, PERIOD_OPTIONS } from "../utils/aiReports";
import { loadSettings, saveSettings, SettingsStatusMessages } from "../utils/settingsPage";

const NOTIFY_ROLES = ["Admin", "Manager", "Sales", "Accountant", "Employee"];

function AiReportsSettings() {
  const role = localStorage.getItem("role") || "Staff";
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadSettings("/ai-reports/settings", setForm, setError);
  }, []);

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const toggleDomain = (domain) => {
    setForm((f) => {
      const domains = f.default_domains_json || [];
      return {
        ...f,
        default_domains_json: domains.includes(domain)
          ? domains.filter((d) => d !== domain)
          : [...domains, domain],
      };
    });
  };

  const toggleRole = (r) => {
    setForm((f) => {
      const roles = f.notify_roles_json || [];
      return { ...f, notify_roles_json: roles.includes(r) ? roles.filter((x) => x !== r) : [...roles, r] };
    });
  };

  const save = (e) => {
    e.preventDefault();
    saveSettings("/ai-reports/settings", form, { setForm, setError, setSaved });
  };

  return (
    <DashboardLayout title="AI Reports settings" roleLabel={role}>
      <div className="crm-panel">
        <Link to="/ai-reports" className="crm-muted">← AI Reports</Link>
        <SettingsStatusMessages error={error} saved={saved} />
        {form && (
          <form className="crm-form crm-mt" onSubmit={save}>
            <div className="crm-form-field">
              <label>
                <input type="checkbox" checked={form.is_enabled} onChange={(e) => setField("is_enabled", e.target.checked)} />
                {" "}Enable AI Reports module
              </label>
            </div>
            <div className="crm-form-field">
              <label>Default period</label>
              <select value={form.default_period} onChange={(e) => setField("default_period", e.target.value)}>
                {PERIOD_OPTIONS.map((p) => (
                  <option key={p} value={p}>{PERIOD_LABELS[p]}</option>
                ))}
              </select>
            </div>
            <div className="crm-form-field">
              <label>Default domains</label>
              <div className="crm-checkbox-group">
                {Object.keys(DOMAIN_LABELS)
                  .filter((d) => d !== "executive")
                  .map((d) => (
                    <label key={d}>
                      <input
                        type="checkbox"
                        checked={(form.default_domains_json || []).includes(d)}
                        onChange={() => toggleDomain(d)}
                      />
                      {" "}{DOMAIN_LABELS[d]}
                    </label>
                  ))}
              </div>
            </div>
            <div className="crm-form-field">
              <label>
                <input
                  type="checkbox"
                  checked={form.include_executive_brief}
                  onChange={(e) => setField("include_executive_brief", e.target.checked)}
                />
                {" "}Include executive brief by default
              </label>
            </div>
            <div className="crm-form-field">
              <label>Notify roles when brief is ready</label>
              <div className="crm-checkbox-group">
                {NOTIFY_ROLES.map((r) => (
                  <label key={r}>
                    <input
                      type="checkbox"
                      checked={(form.notify_roles_json || []).includes(r)}
                      onChange={() => toggleRole(r)}
                    />
                    {" "}{r}
                  </label>
                ))}
              </div>
            </div>
            <div className="crm-form-field">
              <label>Generation mode</label>
              <input value={form.generation_mode || "template"} disabled readOnly />
              <p className="crm-muted">Template-based narratives (Phase 1). LLM enhancement in Phase 2.</p>
            </div>
            <button type="submit" className="crm-btn">Save settings</button>
          </form>
        )}
      </div>
    </DashboardLayout>
  );
}

export default AiReportsSettings;
