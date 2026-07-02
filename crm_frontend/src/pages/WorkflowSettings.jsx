import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { loadSettings, saveSettings, SettingsStatusMessages } from "../utils/settingsPage";

function WorkflowSettings() {
  const role = localStorage.getItem("role") || "Staff";
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadSettings("/workflows/settings", setForm, setError);
  }, []);

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const save = (e) => {
    e.preventDefault();
    saveSettings("/workflows/settings", form, { setForm, setError, setSaved });
  };

  return (
    <DashboardLayout title="Workflow settings" roleLabel={role}>
      <div className="crm-panel">
        <Link to="/workflows" className="crm-muted">← Workflows</Link>
        <SettingsStatusMessages error={error} saved={saved} />
        {form && (
          <form className="crm-form crm-mt" onSubmit={save}>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.is_enabled} onChange={(e) => setField("is_enabled", e.target.checked)} /> Enable Workflow Builder</label>
            </div>
            <div className="crm-form-field"><label>Max active workflows</label><input type="number" min="1" value={form.max_active_workflows} onChange={(e) => setField("max_active_workflows", Number(e.target.value))} /></div>
            <div className="crm-form-field"><label>Rate limit per hour</label><input type="number" min="1" value={form.rate_limit_per_hour} onChange={(e) => setField("rate_limit_per_hour", Number(e.target.value))} /></div>
            <div className="crm-form-field"><label>Run-as role</label><input value={form.default_run_as_role} onChange={(e) => setField("default_run_as_role", e.target.value)} /></div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.notify_on_failure} onChange={(e) => setField("notify_on_failure", e.target.checked)} /> Notify on action failure</label>
            </div>
            <button type="submit" className="crm-btn">Save settings</button>
          </form>
        )}
      </div>
    </DashboardLayout>
  );
}

export default WorkflowSettings;
