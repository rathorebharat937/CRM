import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";
import { loadSettings, saveSettings, SettingsStatusMessages } from "../utils/settingsPage";

const NOTIFY_ROLES = ["Admin", "Manager", "Employee", "Sales", "Accountant"];

function MaintenanceSettings() {
  const role = localStorage.getItem("role") || "Staff";
  const [form, setForm] = useState(null);
  const [categories, setCategories] = useState([]);
  const [newCategory, setNewCategory] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const loadCategories = () => {
    apiFetch("/maintenance/categories").then(setCategories).catch(() => {});
  };

  useEffect(() => {
    loadSettings("/maintenance/settings", setForm, setError);
    loadCategories();
  }, []);

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const toggleRole = (r) => {
    setForm((f) => {
      const roles = f.notify_roles_json || [];
      return {
        ...f,
        notify_roles_json: roles.includes(r) ? roles.filter((x) => x !== r) : [...roles, r],
      };
    });
  };

  const save = (e) => {
    e.preventDefault();
    saveSettings("/maintenance/settings", form, { setForm, setError, setSaved });
  };

  const addCategory = async (e) => {
    e.preventDefault();
    if (!newCategory.trim()) return;
    try {
      await apiFetch("/maintenance/categories", {
        method: "POST",
        body: JSON.stringify({ name: newCategory.trim() }),
      });
      setNewCategory("");
      loadCategories();
      setSaved(false);
      setError("");
    } catch (err) {
      setSaved(false);
      setError(err.message);
    }
  };

  return (
    <DashboardLayout title="Maintenance settings" roleLabel={role}>
      <div className="crm-panel">
        <Link to="/maintenance" className="crm-muted">← Maintenance</Link>
        <SettingsStatusMessages error={error} saved={saved} />
        {form && (
          <form className="crm-form crm-mt" onSubmit={save}>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.is_enabled} onChange={(e) => setField("is_enabled", e.target.checked)} /> Enable maintenance module</label>
            </div>
            <div className="crm-form-field"><label>Work order prefix</label><input value={form.work_order_prefix} onChange={(e) => setField("work_order_prefix", e.target.value)} /></div>
            <div className="crm-form-field"><label>Asset code prefix</label><input value={form.asset_code_prefix} onChange={(e) => setField("asset_code_prefix", e.target.value)} /></div>
            <div className="crm-form-field"><label>Default PM interval (days)</label><input type="number" min="1" value={form.default_pm_interval_days} onChange={(e) => setField("default_pm_interval_days", Number(e.target.value))} /></div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.auto_deduct_spare_parts} onChange={(e) => setField("auto_deduct_spare_parts", e.target.checked)} /> Auto deduct spare parts from inventory</label>
            </div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.allow_negative_spare_parts} onChange={(e) => setField("allow_negative_spare_parts", e.target.checked)} /> Allow negative spare parts stock</label>
            </div>
            <div className="crm-form-field">
              <label>Critical breakdown notify roles</label>
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
        <h3 className="crm-mt">Asset categories</h3>
        <ul className="crm-mt">
          {categories.map((c) => <li key={c.id}>{c.name}</li>)}
        </ul>
        <form className="crm-inline-actions crm-mt" onSubmit={addCategory}>
          <input value={newCategory} onChange={(e) => setNewCategory(e.target.value)} placeholder="New category name" />
          <button type="submit" className="crm-btn crm-btn-sm">Add</button>
        </form>
      </div>
    </DashboardLayout>
  );
}

export default MaintenanceSettings;
