import { useEffect, useState } from "react";

import DashboardLayout from "../components/DashboardLayout";
import { ModuleBackLink } from "../components/ModulePage";
import { loadSettings, saveSettings, SettingsStatusMessages } from "../utils/settingsPage";

function AiAssistantSettings() {
  const role = localStorage.getItem("role") || "Staff";
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadSettings("/ai-assistant/settings", setForm, setError);
  }, []);

  const save = (e) => {
    e.preventDefault();
    saveSettings("/ai-assistant/settings", form, { setForm, setError, setSaved });
  };

  return (
    <DashboardLayout title="AI Assistant settings" roleLabel={role}>
      <div className="crm-panel">
        <ModuleBackLink to="/ai-assistant">← AI Assistant</ModuleBackLink>
        <SettingsStatusMessages error={error} saved={saved} />
        {form && (
          <form className="crm-form crm-mt" onSubmit={save}>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.is_enabled} onChange={(e) => setForm({ ...form, is_enabled: e.target.checked })} /> Enable AI Assistant</label>
            </div>
            <p className="crm-muted">Phase 1 uses built-in rules (no OpenAI key required). Connect an LLM in a future release for richer answers.</p>
            <button type="submit" className="crm-btn crm-btn-inline">Save settings</button>
          </form>
        )}
      </div>
    </DashboardLayout>
  );
}

export default AiAssistantSettings;
