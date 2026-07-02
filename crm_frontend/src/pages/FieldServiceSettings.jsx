import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { loadSettings, saveSettings, SettingsStatusMessages } from "../utils/settingsPage";

const NOTIFY_ROLES = ["Admin", "Manager", "Employee", "Sales", "Accountant"];

function FieldServiceSettings() {
  const role = localStorage.getItem("role") || "Staff";
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadSettings("/field-service/settings", setForm, setError);
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
    saveSettings("/field-service/settings", form, { setForm, setError, setSaved });
  };

  return (
    <DashboardLayout title="Field Service settings" roleLabel={role}>
      <div className="crm-panel">
        <Link to="/field-service" className="crm-muted">← Field Service</Link>
        <SettingsStatusMessages error={error} saved={saved} />
        {form && (
          <form className="crm-form crm-mt" onSubmit={save}>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.is_enabled} onChange={(e) => setField("is_enabled", e.target.checked)} /> Enable field service module</label>
            </div>
            <div className="crm-form-field"><label>Order prefix</label><input value={form.order_prefix} onChange={(e) => setField("order_prefix", e.target.value)} /></div>
            <div className="crm-form-field"><label>Default SLA (hours)</label><input type="number" min="1" value={form.default_sla_hours} onChange={(e) => setField("default_sla_hours", Number(e.target.value))} /></div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.auto_deduct_parts} onChange={(e) => setField("auto_deduct_parts", e.target.checked)} /> Auto deduct parts from inventory</label>
            </div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.allow_negative_parts} onChange={(e) => setField("allow_negative_parts", e.target.checked)} /> Allow negative parts stock</label>
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

export default FieldServiceSettings;
