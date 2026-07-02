import { useEffect, useState } from "react";

import { apiFetch } from "../utils/api";
import { hasPermission } from "../utils/permissions";

function RemindersPanel({ leadId, dealId, contactId, compact = false }) {
  const [reminders, setReminders] = useState([]);
  const [types, setTypes] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    title: "",
    reminder_type: "call",
    priority: "normal",
    due_at: "",
    notes: "",
  });

  const canCreate = hasPermission("reminders.create");
  const canEdit = hasPermission("reminders.edit");

  const params = new URLSearchParams({ status: "pending", limit: "10" });
  if (leadId) params.set("lead_id", String(leadId));
  if (dealId) params.set("deal_id", String(dealId));
  if (contactId) params.set("contact_id", String(contactId));

  const load = () => {
    apiFetch(`/reminders?${params}`).then((data) => setReminders(data.items)).catch(() => {});
  };

  useEffect(() => {
    if (!hasPermission("reminders.view")) return;
    load();
    apiFetch("/reminders/types").then(setTypes).catch(() => {});
  }, [leadId, dealId, contactId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await apiFetch("/reminders", {
        method: "POST",
        body: JSON.stringify({
          title: form.title.trim(),
          reminder_type: form.reminder_type,
          priority: form.priority,
          due_at: new Date(form.due_at).toISOString(),
          notes: form.notes || null,
          lead_id: leadId || null,
          deal_id: dealId || null,
          contact_id: contactId || null,
        }),
      });
      setForm({ title: "", reminder_type: "call", priority: "normal", due_at: "", notes: "" });
      setShowForm(false);
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleComplete = async (id) => {
    try {
      await apiFetch(`/reminders/${id}/complete`, { method: "PATCH" });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (!hasPermission("reminders.view")) return null;

  return (
    <section className={`crm-entity-section ${compact ? "" : "crm-mt-lg"}`.trim()}>
      <div className="crm-detail-header">
        <h3>Follow-up reminders</h3>
        {canCreate && (
          <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={() => setShowForm(!showForm)}>
            {showForm ? "Cancel" : "+ Add reminder"}
          </button>
        )}
      </div>

      {error && <p className="crm-error crm-mt">{error}</p>}

      {showForm && canCreate && (
        <form onSubmit={handleSubmit} className="crm-form crm-note-quick-form crm-mt">
          <div className="crm-form-grid">
            <div className="crm-span-2">
              <label>Title *</label>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
            </div>
            <div>
              <label>Type</label>
              <select value={form.reminder_type} onChange={(e) => setForm({ ...form, reminder_type: e.target.value })}>
                {types.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label>Due at *</label>
              <input type="datetime-local" value={form.due_at} onChange={(e) => setForm({ ...form, due_at: e.target.value })} required />
            </div>
            <div>
              <label>Priority</label>
              <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
          </div>
          <button type="submit" className="crm-btn crm-btn-sm crm-btn-inline">Save reminder</button>
        </form>
      )}

      {reminders.length === 0 ? (
        <p className="crm-muted crm-mt">No pending reminders.</p>
      ) : (
        <ul className="crm-reminder-list">
          {reminders.map((r) => (
            <li key={r.id} className="crm-reminder-item">
              <div className="crm-reminder-main">
                <strong className="crm-reminder-title">{r.title}</strong>
                <p className="crm-reminder-meta">
                  <span>{r.reminder_type_label}</span>
                  <span aria-hidden="true">·</span>
                  <span>{new Date(r.due_at).toLocaleString()}</span>
                </p>
              </div>
              <div className="crm-reminder-actions">
                {r.is_overdue && <span className="crm-badge crm-deal-lost">Overdue</span>}
                {canEdit && (
                  <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={() => handleComplete(r.id)}>
                    Done
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default RemindersPanel;
