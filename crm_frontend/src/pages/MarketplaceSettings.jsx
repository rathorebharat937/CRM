import { useEffect, useState } from "react";

import DashboardLayout from "../components/DashboardLayout";
import { ModuleBackLink } from "../components/ModulePage";
import { loadSettings, saveSettings, SettingsStatusMessages } from "../utils/settingsPage";

function MarketplaceSettings() {
  const role = localStorage.getItem("role") || "Staff";
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadSettings("/marketplace/settings", setForm, setError);
  }, []);

  const save = (e) => {
    e.preventDefault();
    saveSettings("/marketplace/settings", form, { setForm, setError, setSaved });
  };

  return (
    <DashboardLayout title="Marketplace settings" roleLabel={role}>
      <div className="crm-panel">
        <ModuleBackLink to="/marketplace">← Marketplace</ModuleBackLink>
        <SettingsStatusMessages error={error} saved={saved} />
        {form && (
          <form className="crm-form crm-mt" onSubmit={save}>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.is_enabled} onChange={(e) => setForm({ ...form, is_enabled: e.target.checked })} /> Enable API Marketplace</label>
            </div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.public_api_enabled} onChange={(e) => setForm({ ...form, public_api_enabled: e.target.checked })} /> Allow REST API access (keys required)</label>
            </div>
            <p className="crm-muted">Outbound connectors store config only until live credentials are added (Razorpay, WhatsApp, etc.).</p>
            <button type="submit" className="crm-btn crm-btn-inline">Save settings</button>
          </form>
        )}
      </div>
    </DashboardLayout>
  );
}

export default MarketplaceSettings;
