import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { loadSettings, saveSettings, SettingsStatusMessages } from "../utils/settingsPage";

const NOTIFY_ROLES = ["Admin", "Manager", "Employee", "Sales", "Accountant"];

function RentalSettings() {
  const role = localStorage.getItem("role") || "Staff";
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadSettings("/rental/settings", setForm, setError);
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
    saveSettings("/rental/settings", form, { setForm, setError, setSaved });
  };

  return (
    <DashboardLayout title="Rental settings" roleLabel={role}>
      <div className="crm-panel">
        <Link to="/rental" className="crm-muted">← Rental</Link>
        <SettingsStatusMessages error={error} saved={saved} />
        {form && (
          <form className="crm-form crm-mt" onSubmit={save}>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.is_enabled} onChange={(e) => setField("is_enabled", e.target.checked)} /> Enable rental module</label>
            </div>
            <div className="crm-form-field"><label>Contract prefix</label><input value={form.contract_prefix} onChange={(e) => setField("contract_prefix", e.target.value)} /></div>
            <div className="crm-form-row">
              <div className="crm-form-field">
                <label>Default rate basis</label>
                <select value={form.default_rate_basis} onChange={(e) => setField("default_rate_basis", e.target.value)}>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>
              <div className="crm-form-field"><label>Deposit %</label><input type="number" value={form.default_deposit_percent} onChange={(e) => setField("default_deposit_percent", Number(e.target.value))} /></div>
              <div className="crm-form-field"><label>Late fee / day</label><input type="number" value={form.late_fee_per_day} onChange={(e) => setField("late_fee_per_day", Number(e.target.value))} /></div>
              <div className="crm-form-field"><label>Grace hours</label><input type="number" value={form.grace_hours_after_due} onChange={(e) => setField("grace_hours_after_due", Number(e.target.value))} /></div>
            </div>
            <div className="crm-form-field">
              <label>Auto invoice mode</label>
              <select value={form.auto_invoice_mode} onChange={(e) => setField("auto_invoice_mode", e.target.value)}>
                <option value="draft">Draft</option>
                <option value="issue">Issue immediately</option>
              </select>
            </div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.require_deposit_before_delivery} onChange={(e) => setField("require_deposit_before_delivery", e.target.checked)} /> Require deposit before delivery</label>
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

export default RentalSettings;
