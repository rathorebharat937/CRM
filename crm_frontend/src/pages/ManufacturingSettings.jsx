import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { loadSettings, saveSettings, SettingsStatusMessages } from "../utils/settingsPage";

function ManufacturingSettings() {
  const role = localStorage.getItem("role") || "Staff";
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadSettings("/manufacturing/settings", setForm, setError);
  }, []);

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const save = (e) => {
    e.preventDefault();
    saveSettings("/manufacturing/settings", form, { setForm, setError, setSaved });
  };

  return (
    <DashboardLayout title="Manufacturing settings" roleLabel={role}>
      <div className="crm-panel">
        <Link to="/manufacturing" className="crm-muted">← Manufacturing</Link>
        <SettingsStatusMessages error={error} saved={saved} />
        {form && (
          <form className="crm-form crm-mt" onSubmit={save}>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.is_enabled} onChange={(e) => setField("is_enabled", e.target.checked)} /> Enable manufacturing module</label>
            </div>
            <div className="crm-form-field"><label>Work order prefix</label><input value={form.work_order_prefix} onChange={(e) => setField("work_order_prefix", e.target.value)} /></div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.require_qc_before_receipt} onChange={(e) => setField("require_qc_before_receipt", e.target.checked)} /> Require QC before FG receipt</label>
            </div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.auto_reserve_materials_on_release} onChange={(e) => setField("auto_reserve_materials_on_release", e.target.checked)} /> Auto-reserve materials on release</label>
            </div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.allow_negative_issue} onChange={(e) => setField("allow_negative_issue", e.target.checked)} /> Allow negative stock on issue</label>
            </div>
            <div className="crm-form-field"><label>Default scrap %</label><input type="number" min="0" value={form.default_scrap_pct} onChange={(e) => setField("default_scrap_pct", Number(e.target.value))} /></div>
            <button type="submit" className="crm-btn">Save</button>
          </form>
        )}
      </div>
    </DashboardLayout>
  );
}

export default ManufacturingSettings;
