import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";
import { hasPermission } from "../utils/permissions";
import {
  NOTE_TYPE_LABELS,
  VISIBILITY_LABELS,
  emptyNoteForm,
  formatDateTime,
  noteTypeBadgeClass,
} from "../utils/clientNotes";

function ClientNotes() {
  const [searchParams, setSearchParams] = useSearchParams();
  const role = localStorage.getItem("role") || "Staff";
  const [data, setData] = useState({ items: [], total: 0, page: 1, limit: 20 });
  const [stats, setStats] = useState(null);
  const [types, setTypes] = useState([]);
  const [search, setSearch] = useState(searchParams.get("search") || "");
  const [noteType, setNoteType] = useState(searchParams.get("note_type") || "");
  const [pinnedOnly, setPinnedOnly] = useState(searchParams.get("pinned") === "true");
  const [followUpOnly, setFollowUpOnly] = useState(searchParams.get("follow_up") === "true");
  const [contactId, setContactId] = useState(searchParams.get("contact_id") || "");
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState({});

  // Create note modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState(emptyNoteForm());
  const [createError, setCreateError] = useState("");
  const [createMessage, setCreateMessage] = useState("");
  const modalScrollRef = useRef(null);

  // Lock body scroll while modal is open
  useEffect(() => {
    if (showCreateModal) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [showCreateModal]);

  const contactFilter = searchParams.get("contact_id") || contactId;

  useEffect(() => {
    apiFetch("/client-notes/types").then(setTypes).catch(() => {});
    apiFetch("/client-notes/stats/summary").then(setStats).catch(() => {});
  }, []);

  const load = (page = 1) => {
    const params = new URLSearchParams({ page: String(page), limit: "20" });
    if (contactFilter) params.set("contact_id", contactFilter);
    if (noteType) params.set("note_type", noteType);
    if (pinnedOnly) params.set("pinned", "true");
    if (followUpOnly) params.set("follow_up_required", "true");
    if (search.trim()) params.set("search", search.trim());
    apiFetch(`/client-notes?${params}`)
      .then(setData)
      .catch((err) => setError(err.message));
  };

  useEffect(() => {
    load(1);
  }, [noteType, pinnedOnly, followUpOnly, contactFilter]);

  const handleSearch = (e) => {
    e.preventDefault();
    load(1);
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    setCreateError("");
    setCreateMessage("");
    try {
      await apiFetch("/client-notes", {
        method: "POST",
        body: JSON.stringify({
          note_type: createForm.note_type,
          title: createForm.title.trim(),
          body: createForm.body.trim(),
          visibility_scope: createForm.visibility_scope,
          tags: createForm.tags.trim() || null,
          is_pinned: createForm.is_pinned,
          is_sensitive: createForm.is_sensitive || createForm.visibility_scope === "sensitive",
          follow_up_required: createForm.follow_up_required,
          follow_up_due_date: createForm.follow_up_due_date
            ? new Date(`${createForm.follow_up_due_date}T12:00:00`).toISOString()
            : null,
          follow_up_priority: createForm.follow_up_priority,
        }),
      });
      setCreateMessage("Note created successfully.");
      setCreateForm(emptyNoteForm());
      setShowCreateModal(false);
      load(1);
      apiFetch("/client-notes/stats/summary").then(setStats).catch(() => {});
    } catch (err) {
      setCreateError(err.message);
    }
  };

  const totalPages = Math.max(1, Math.ceil(data.total / data.limit));

  return (
    <DashboardLayout title="Client Notes" roleLabel={role}>
      <div className="crm-panel">
        <div className="crm-detail-header">
          <p className="crm-meta-sub">{data.total} note{data.total === 1 ? "" : "s"}</p>
          <div className="crm-inline-actions">
            {hasPermission("client_notes.create") && (
              <button
                type="button"
                className="crm-btn crm-btn-sm"
                onClick={() => { setShowCreateModal(true); setCreateError(""); setCreateMessage(""); }}
              >
                + Create client note
              </button>
            )}
            {hasPermission("client_notes.manage_followups") && (
              <Link to="/client-notes/follow-ups" className="crm-btn crm-btn-sm crm-btn-outline">Follow-up queue</Link>
            )}
          </div>
        </div>

        {createMessage && <p className="crm-success crm-mt">{createMessage}</p>}

        {stats && (
          <div className="crm-stat-strip crm-mt">
            <div className="crm-stat-card">
              <span className="crm-stat-label">Total</span>
              <strong>{stats.total}</strong>
            </div>
            <div className="crm-stat-card">
              <span className="crm-stat-label">Pinned</span>
              <strong>{stats.pinned}</strong>
            </div>
            <div className="crm-stat-card">
              <span className="crm-stat-label">Follow-ups</span>
              <strong>{stats.follow_up_pending}</strong>
            </div>
            <div className="crm-stat-card crm-stat-warn">
              <span className="crm-stat-label">Overdue</span>
              <strong>{stats.follow_up_overdue}</strong>
            </div>
          </div>
        )}

        <form onSubmit={handleSearch} className="crm-filter-bar crm-mt">
          <input
            placeholder="Search notes…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select value={noteType} onChange={(e) => setNoteType(e.target.value)}>
            <option value="">All types</option>
            {types.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <label className="crm-consent-check">
            <input type="checkbox" checked={pinnedOnly} onChange={(e) => setPinnedOnly(e.target.checked)} />
            Pinned only
          </label>
          <label className="crm-consent-check">
            <input type="checkbox" checked={followUpOnly} onChange={(e) => setFollowUpOnly(e.target.checked)} />
            Follow-up required
          </label>
          <button type="submit" className="crm-btn crm-btn-sm">Search</button>
        </form>

        {contactFilter && (
          <p className="crm-mt">
            Filtered by contact #{contactFilter}
            <button type="button" className="crm-link crm-btn-link crm-ml" onClick={() => { setContactId(""); setSearchParams({}); }}>Clear</button>
          </p>
        )}

        {error && <p className="crm-error crm-mt">{error}</p>}

        {data.items.length === 0 && <p className="crm-muted crm-mt">No notes found.</p>}

        <div className="crm-note-timeline crm-mt-lg">
          {data.items.map((note) => (
            <div key={note.id} className={`crm-note-card ${note.is_pinned ? "crm-note-card-pinned" : ""} ${note.follow_up_overdue ? "crm-note-card-overdue" : ""}`}>
              <div className="crm-note-card-header">
                <span className={noteTypeBadgeClass(note.note_type)}>{NOTE_TYPE_LABELS[note.note_type]}</span>
                {note.is_pinned && <span className="crm-badge crm-note-pinned">Pinned</span>}
                {note.is_sensitive && <span className="crm-badge crm-note-sensitive">Sensitive</span>}
                <span className="crm-muted">{formatDateTime(note.created_at)}</span>
              </div>
              <strong>{note.title}</strong>
              {note.contact_name && (
                <p className="crm-text-secondary">
                  {note.contact_id ? (
                    <Link to={`/contacts/${note.contact_id}`} className="crm-nav-link">{note.contact_name}</Link>
                  ) : note.contact_name}
                </p>
              )}
              <p className="crm-note-excerpt">
                {expanded[note.id] ? note.body : (note.body.length > 240 ? `${note.body.slice(0, 240)}…` : note.body)}
              </p>
              {note.body.length > 240 && (
                <button type="button" className="crm-link crm-btn-link" onClick={() => setExpanded({ ...expanded, [note.id]: !expanded[note.id] })}>
                  {expanded[note.id] ? "Show less" : "Show more"}
                </button>
              )}
              <div className="crm-note-card-links">
                {note.deal_id && <Link to={`/deals/${note.deal_id}`} className="crm-nav-link">Deal</Link>}
                {note.quotation_id && <Link to={`/quotations/${note.quotation_id}`} className="crm-nav-link">Quote</Link>}
                {note.sales_order_id && <Link to={`/sales-orders/${note.sales_order_id}`} className="crm-nav-link">Order</Link>}
                {note.invoice_id && <Link to={`/invoices/${note.invoice_id}`} className="crm-nav-link">Invoice</Link>}
              </div>
              <div className="crm-note-card-meta">
                {note.author_name} · {VISIBILITY_LABELS[note.visibility_scope]}
                {note.revision_count > 0 && " · Edited"}
              </div>
            </div>
          ))}
        </div>

        {totalPages > 1 && (
          <div className="crm-pagination crm-mt">
            <button type="button" className="crm-btn crm-btn-outline crm-btn-sm" disabled={data.page <= 1} onClick={() => load(data.page - 1)}>Previous</button>
            <span className="crm-muted">Page {data.page} of {totalPages}</span>
            <button type="button" className="crm-btn crm-btn-outline crm-btn-sm" disabled={data.page >= totalPages} onClick={() => load(data.page + 1)}>Next</button>
          </div>
        )}
      </div>

      {/* Create Client Note Modal */}
      {showCreateModal && (
        <div
          className="crm-note-modal-overlay"
          onClick={() => setShowCreateModal(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="create-note-modal-title"
        >
          <div
            className="crm-note-modal"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="crm-note-modal-header">
              <h3 id="create-note-modal-title" className="crm-note-modal-title">
                Create Client Note
              </h3>
              <button
                type="button"
                className="crm-note-modal-close"
                onClick={() => setShowCreateModal(false)}
                aria-label="Close"
              >
                ×
              </button>
            </div>

            {/* Scrollable body */}
            <div className="crm-note-modal-body" ref={modalScrollRef}>
              {createError && (
                <p className="crm-error" style={{ marginBottom: "4px" }}>{createError}</p>
              )}

              <form onSubmit={handleCreateSubmit} className="crm-form">
                {/* Row 1: Type + Visibility */}
                <div className="crm-form-grid">
                  <div className="crm-form-field">
                    <label htmlFor="cn-type">Type</label>
                    <select
                      id="cn-type"
                      value={createForm.note_type}
                      onChange={(e) => setCreateForm({ ...createForm, note_type: e.target.value })}
                    >
                      {(types.length
                        ? types
                        : Object.entries(NOTE_TYPE_LABELS).map(([value, label]) => ({ value, label }))
                      ).map((t) => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="crm-form-field">
                    <label htmlFor="cn-visibility">Visibility</label>
                    <select
                      id="cn-visibility"
                      value={createForm.visibility_scope}
                      onChange={(e) => setCreateForm({ ...createForm, visibility_scope: e.target.value })}
                    >
                      {Object.entries(VISIBILITY_LABELS).map(([k, v]) => (
                        <option key={k} value={k}>{v}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Summary */}
                <div className="crm-form-field">
                  <label htmlFor="cn-title">Summary *</label>
                  <input
                    id="cn-title"
                    value={createForm.title}
                    onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })}
                    placeholder="Short summary…"
                    required
                  />
                </div>

                {/* Note body */}
                <div className="crm-form-field">
                  <label htmlFor="cn-body">Note *</label>
                  <textarea
                    id="cn-body"
                    rows={5}
                    value={createForm.body}
                    onChange={(e) => setCreateForm({ ...createForm, body: e.target.value })}
                    placeholder="Capture call details, requirements, objections…"
                    required
                  />
                </div>

                {/* Flags */}
                <div className="crm-note-form-flags">
                  <label className="crm-consent-check">
                    <input
                      type="checkbox"
                      checked={createForm.follow_up_required}
                      onChange={(e) => setCreateForm({ ...createForm, follow_up_required: e.target.checked })}
                    />
                    Follow-up required
                  </label>
                  {createForm.follow_up_required && (
                    <input
                      type="date"
                      className="crm-note-modal-date"
                      value={createForm.follow_up_due_date}
                      onChange={(e) => setCreateForm({ ...createForm, follow_up_due_date: e.target.value })}
                    />
                  )}
                  <label className="crm-consent-check">
                    <input
                      type="checkbox"
                      checked={createForm.is_pinned}
                      onChange={(e) => setCreateForm({ ...createForm, is_pinned: e.target.checked })}
                    />
                    Pin as key insight
                  </label>
                </div>

                {/* Actions */}
                <div className="crm-note-modal-actions">
                  <button type="submit" className="crm-btn crm-btn-sm">
                    Save note
                  </button>
                  <button
                    type="button"
                    className="crm-btn crm-btn-sm crm-btn-outline"
                    onClick={() => setShowCreateModal(false)}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

export default ClientNotes;
