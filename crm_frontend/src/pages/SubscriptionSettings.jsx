import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { loadSettings, saveSettings, SettingsStatusMessages } from "../utils/settingsPage";

const NOTIFY_ROLES = ["Admin", "Manager", "Employee", "Sales", "Accountant"];

function SubscriptionSettings() {
  const role = localStorage.getItem("role") || "Staff";
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadSettings("/subscriptions/settings", setForm, setError);
  }, []);

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const toggleRole = (r) => {
    setForm((f) => {
      const roles = f.notify_roles_json || [];
      return { ...f, notify_roles_json: roles.includes(r) ? roles.filter((x) => x !== r) : [...roles, r] };
    });
  };

  const save = (e) => {
    e.preventDefault();
    saveSettings("/subscriptions/settings", form, { setForm, setError, setSaved });
  };

  return (
    <DashboardLayout title="Subscription settings" roleLabel={role}>
      <div className="crm-panel">
        <Link to="/subscriptions" className="crm-muted">← Subscriptions</Link>
        <SettingsStatusMessages error={error} saved={saved} />
        {form && (
          <form className="crm-form crm-mt" onSubmit={save}>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.is_enabled} onChange={(e) => setField("is_enabled", e.target.checked)} /> Enable subscriptions module</label>
            </div>
            <div className="crm-form-field"><label>Subscription prefix</label><input value={form.subscription_prefix} onChange={(e) => setField("subscription_prefix", e.target.value)} /></div>
            <div className="crm-form-field">
              <label>Reminder days (comma-separated)</label>
              <input
                value={(form.default_reminder_days || []).join(", ")}
                onChange={(e) => setField("default_reminder_days", e.target.value.split(",").map((x) => Number(x.trim())).filter((n) => !Number.isNaN(n)))}
              />
            </div>
            <div className="crm-form-field">
              <label>Auto invoice mode</label>
              <select value={form.auto_invoice_mode} onChange={(e) => setField("auto_invoice_mode", e.target.value)}>
                <option value="draft">Draft</option>
                <option value="issue">Issue immediately</option>
              </select>
            </div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.auto_invoice_on_billing_date} onChange={(e) => setField("auto_invoice_on_billing_date", e.target.checked)} /> Auto invoice on billing date (manual run Phase 1)</label>
            </div>
            <div className="crm-form-field"><label>Grace period (days)</label><input type="number" min="0" value={form.grace_period_days} onChange={(e) => setField("grace_period_days", Number(e.target.value))} /></div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.allow_immediate_cancel} onChange={(e) => setField("allow_immediate_cancel", e.target.checked)} /> Allow immediate cancellation</label>
            </div>
            <div className="crm-form-field">
              <label>Alert notify roles</label>
              <div className="crm-checkbox-group">
                {NOTIFY_ROLES.map((r) => (
                  <label key={r}>
                    <input type="checkbox" checked={(form.notify_roles_json || []).includes(r)} onChange={() => toggleRole(r)} /> {r}
                  </label>
                ))}
              </div>
            </div>
            <button type="submit" className="crm-btn">Save settings</button>
          </form>
        )}
      </div>
    </DashboardLayout>
  );
}

export default SubscriptionSettings;
