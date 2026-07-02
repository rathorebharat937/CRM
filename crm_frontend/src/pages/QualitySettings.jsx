import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { loadSettings, saveSettings, SettingsStatusMessages } from "../utils/settingsPage";

function QualitySettings() {
  const role = localStorage.getItem("role") || "Staff";
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadSettings("/quality/settings", setForm, setError);
  }, []);

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const save = (e) => {
    e.preventDefault();
    saveSettings("/quality/settings", form, { setForm, setError, setSaved });
  };

  return (
    <DashboardLayout title="Quality settings" roleLabel={role}>
      <div className="crm-panel">
        <Link to="/quality" className="crm-muted">← Quality Control</Link>
        <SettingsStatusMessages error={error} saved={saved} />
        {form && (
          <form className="crm-form crm-mt" onSubmit={save}>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.is_enabled} onChange={(e) => setField("is_enabled", e.target.checked)} /> Enable Quality Control</label>
            </div>
            <div className="crm-form-field"><label>Inspection prefix</label><input value={form.inspection_number_prefix} onChange={(e) => setField("inspection_number_prefix", e.target.value)} /></div>
            <div className="crm-form-field"><label>CAPA prefix</label><input value={form.capa_number_prefix} onChange={(e) => setField("capa_number_prefix", e.target.value)} /></div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.default_incoming_required} onChange={(e) => setField("default_incoming_required", e.target.checked)} /> Incoming QC on PO receipt</label>
            </div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.block_on_fail_default} onChange={(e) => setField("block_on_fail_default", e.target.checked)} /> Block downstream on fail</label>
            </div>
            <div className="crm-form-field"><label>Repeat-fail threshold (30d)</label><input type="number" min="2" value={form.alert_repeat_fail_threshold} onChange={(e) => setField("alert_repeat_fail_threshold", Number(e.target.value))} /></div>
            <div className="crm-form-field"><label>Overdue inspection hours</label><input type="number" min="1" value={form.alert_overdue_hours} onChange={(e) => setField("alert_overdue_hours", Number(e.target.value))} /></div>
            <button type="submit" className="crm-btn">Save</button>
          </form>
        )}
      </div>
    </DashboardLayout>
  );
}

export default QualitySettings;
