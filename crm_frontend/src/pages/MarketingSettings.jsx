import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { ModuleBackLink } from "../components/ModulePage";
import { loadSettings, saveSettings, SettingsStatusMessages } from "../utils/settingsPage";

function MarketingSettings() {
  const role = localStorage.getItem("role") || "Staff";
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadSettings("/marketing/settings", setForm, setError);
  }, []);

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const save = (e) => {
    e.preventDefault();
    saveSettings("/marketing/settings", form, { setForm, setError, setSaved });
  };

  return (
    <DashboardLayout title="Marketing settings" roleLabel={role}>
      <div className="crm-panel">
        <ModuleBackLink to="/marketing">← Marketing</ModuleBackLink>
        <SettingsStatusMessages error={error} saved={saved} />
        {form && (
          <form className="crm-form crm-mt" onSubmit={save}>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.is_enabled} onChange={(e) => setField("is_enabled", e.target.checked)} /> Enable Marketing Automation</label>
            </div>
            <div className="crm-form-field">
              <label>Default owner role for reminders</label>
              <input value={form.default_owner_role} onChange={(e) => setField("default_owner_role", e.target.value)} />
            </div>
            <button type="submit" className="crm-btn crm-btn-inline">Save settings</button>
          </form>
        )}
      </div>
    </DashboardLayout>
  );
}

export default MarketingSettings;
