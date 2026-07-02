import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiFetch } from "../utils/api";
import { hasPermission } from "../utils/permissions";
import {
  NOTE_TYPE_LABELS,
  VISIBILITY_LABELS,
  buildNoteQuery,
  emptyNoteForm,
  formatDateTime,
  noteTypeBadgeClass,
} from "../utils/clientNotes";

function ClientNotesPanel({
  contactId,
  leadId,
  dealId,
  quotationId,
  salesOrderId,
  invoiceId,
  contactName,
  compact = false,
  title = "Client notes",
}) {
  const [notes, setNotes] = useState([]);
  const [types, setTypes] = useState([]);
  const [form, setForm] = useState(emptyNoteForm());
  const [expanded, setExpanded] = useState({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  const canCreate = hasPermission("client_notes.create");
  const canPin = hasPermission("client_notes.pin");
  const canEdit = hasPermission("client_notes.edit_own") || hasPermission("client_notes.edit_all");
  const canFollowUp = hasPermission("client_notes.manage_followups");

  const context = { contactId, leadId, dealId, quotationId, salesOrderId, invoiceId };
  const query = buildNoteQuery(context);

  const load = () => {
    const limit = compact ? 5 : 20;
    apiFetch(`/client-notes?${query}&limit=${limit}`)
      .then((data) => setNotes(data.items || []))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    apiFetch("/client-notes/types").then(setTypes).catch(() => {});
    load();
  }, [contactId, leadId, dealId, quotationId, salesOrderId, invoiceId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setMessage("");
    try {
      await apiFetch("/client-notes", {
        method: "POST",
        body: JSON.stringify({
          contact_id: contactId || null,
          lead_id: leadId || null,
          deal_id: dealId || null,
          quotation_id: quotationId || null,
          sales_order_id: salesOrderId || null,
          invoice_id: invoiceId || null,
          note_type: form.note_type,
          title: form.title.trim(),
          body: form.body.trim(),
          visibility_scope: form.visibility_scope,
          tags: form.tags.trim() || null,
          is_pinned: form.is_pinned,
          is_sensitive: form.is_sensitive || form.visibility_scope === "sensitive",
          follow_up_required: form.follow_up_required,
          follow_up_due_date: form.follow_up_due_date
            ? new Date(`${form.follow_up_due_date}T12:00:00`).toISOString()
            : null,
          follow_up_priority: form.follow_up_priority,
        }),
      });
      setForm(emptyNoteForm());
      setMessage("Note saved.");
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const runAction = async (path, msg) => {
    setError("");
    try {
      await apiFetch(path, { method: "POST" });
      setMessage(msg);
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const pinned = notes.filter((n) => n.is_pinned);
  const regular = notes.filter((n) => !n.is_pinned);
  const timelineLink = contactId
    ? `/client-notes?contact_id=${contactId}`
    : `/client-notes?${query}`;

  return (
    <section className="crm-entity-section crm-client-notes-panel">
      <div className="crm-detail-header">
        <h3>{title}</h3>
        <Link to={timelineLink} className="crm-nav-link">View all</Link>
      </div>

      {contactName && <p className="crm-text-secondary">{contactName}</p>}
      {message && <p className="crm-success crm-mt">{message}</p>}
      {error && <p className="crm-error crm-mt">{error}</p>}

      {pinned.length > 0 && (
        <div className="crm-note-pinned-section crm-mt">
          <h4 className="crm-note-section-label">Pinned insights</h4>
          {pinned.map((note) => (
            <div key={note.id} className="crm-note-card crm-note-card-pinned">
              <div className="crm-note-card-header">
                <span className={noteTypeBadgeClass(note.note_type)}>{NOTE_TYPE_LABELS[note.note_type]}</span>
                <strong>{note.title}</strong>
              </div>
              <p className="crm-note-excerpt">{note.body}</p>
            </div>
          ))}
        </div>
      )}

      {canCreate && (
        <form onSubmit={handleSubmit} className="crm-form crm-note-quick-form crm-mt">
          <div className="crm-form-grid">
            <div>
              <label>Type</label>
              <select value={form.note_type} onChange={(e) => setForm({ ...form, note_type: e.target.value })}>
                {(types.length ? types : Object.entries(NOTE_TYPE_LABELS).map(([value, label]) => ({ value, label }))).map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label>Visibility</label>
              <select value={form.visibility_scope} onChange={(e) => setForm({ ...form, visibility_scope: e.target.value })}>
                {Object.entries(VISIBILITY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
          </div>
          <label>Summary</label>
          <input
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="Short summary…"
            required
          />
          <label>Note</label>
          <textarea
            className="crm-textarea"
            rows={compact ? 2 : 3}
            value={form.body}
            onChange={(e) => setForm({ ...form, body: e.target.value })}
            placeholder="Capture call details, requirements, objections…"
            required
          />
          <div className="crm-note-form-flags">
            <label className="crm-consent-check">
              <input type="checkbox" checked={form.follow_up_required} onChange={(e) => setForm({ ...form, follow_up_required: e.target.checked })} />
              Follow-up required
            </label>
            {form.follow_up_required && (
              <input type="date" value={form.follow_up_due_date} onChange={(e) => setForm({ ...form, follow_up_due_date: e.target.value })} />
            )}
            {canPin && (
              <label className="crm-consent-check">
                <input type="checkbox" checked={form.is_pinned} onChange={(e) => setForm({ ...form, is_pinned: e.target.checked })} />
                Pin as key insight
              </label>
            )}
          </div>
          <button type="submit" className="crm-btn crm-btn-sm crm-btn-inline">Save note</button>
        </form>
      )}

      {loading && <p className="crm-muted crm-mt">Loading notes…</p>}

      {!loading && notes.length === 0 && (
        <p className="crm-muted crm-mt">No client notes yet. Capture the first interaction to build relationship memory.</p>
      )}

      <div className="crm-note-timeline crm-mt">
        {regular.map((note) => (
          <div key={note.id} className={`crm-note-card ${note.follow_up_overdue ? "crm-note-card-overdue" : ""}`}>
            <div className="crm-note-card-header">
              <span className={noteTypeBadgeClass(note.note_type)}>{NOTE_TYPE_LABELS[note.note_type]}</span>
              {note.is_sensitive && <span className="crm-badge crm-note-sensitive">Sensitive</span>}
              {note.follow_up_required && !note.follow_up_completed_at && (
                <span className="crm-badge crm-note-follow_up">Follow-up</span>
              )}
              {note.is_resolved && <span className="crm-badge crm-note-resolved">Resolved</span>}
              <span className="crm-muted">{formatDateTime(note.created_at)}</span>
            </div>
            <strong>{note.title}</strong>
            <p className="crm-note-excerpt">
              {expanded[note.id] ? note.body : (note.body.length > 180 ? `${note.body.slice(0, 180)}…` : note.body)}
            </p>
            {note.body.length > 180 && (
              <button type="button" className="crm-link crm-btn-link" onClick={() => setExpanded({ ...expanded, [note.id]: !expanded[note.id] })}>
                {expanded[note.id] ? "Show less" : "Show more"}
              </button>
            )}
            <div className="crm-note-card-meta crm-muted">
              {note.author_name} · {VISIBILITY_LABELS[note.visibility_scope]}
              {note.revision_count > 0 && " · Edited"}
              {note.tags && ` · ${note.tags}`}
            </div>
            {(canPin || canFollowUp) && (
              <div className="crm-inline-actions crm-mt">
                {canPin && !note.is_pinned && (
                  <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={() => runAction(`/client-notes/${note.id}/pin`, "Pinned")}>Pin</button>
                )}
                {canPin && note.is_pinned && (
                  <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={() => runAction(`/client-notes/${note.id}/unpin`, "Unpinned")}>Unpin</button>
                )}
                {canFollowUp && note.follow_up_required && !note.follow_up_completed_at && (
                  <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={() => runAction(`/client-notes/${note.id}/complete-followup`, "Follow-up completed")}>Complete follow-up</button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

export default ClientNotesPanel;
