import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import ClientNotesPanel from "../components/ClientNotesPanel";
import RemindersPanel from "../components/RemindersPanel";
import DocumentsPanel from "../components/DocumentsPanel";
import { apiFetch } from "../utils/api";
import { hasPermission } from "../utils/permissions";


const STATUS_LABELS = {
  open: "Open",
  hot: "Hot",
  follow_up: "Follow up",
  cold: "Cold",
  lost: "Lost",
  qualified: "Qualified",
  converted: "Converted",
};

function LeadDetail() {
  const { id } = useParams();
  const role = localStorage.getItem("role") || "Staff";
  const canEdit = hasPermission("leads.edit");
  const canCreateDeal = hasPermission("deals.create");
  const canCreateQuote = hasPermission("quotations.create");
  const [lead, setLead] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const loadLead = () => {
    apiFetch(`/leads/${id}`).then(setLead).catch((err) => setError(err.message));
  };

  useEffect(() => {
    loadLead();
  }, [id]);

  const handleCreateDeal = async () => {
    setMessage("");
    setError("");
    try {
      const deal = await apiFetch(`/deals/from-lead/${id}`, { method: "POST" });
      window.location.href = `/deals/${deal.id}`;
    } catch (err) {
      setError(err.message);
    }
  };

  const handleConvert = async () => {
    if (!window.confirm("Convert this lead to a client contact?")) return;
    setMessage("");
    setError("");
    try {
      const result = await apiFetch(`/leads/${id}/convert-to-contact`, { method: "POST" });
      setMessage(result.message);
      setLead(result.lead);
    } catch (err) {
      setError(err.message);
    }
  };

  if (!lead && !error) {
    return (
      <DashboardLayout title="Lead" roleLabel={role}>
        <div className="crm-panel"><p>Loading…</p></div>
      </DashboardLayout>
    );
  }

  if (error && !lead) {
    return (
      <DashboardLayout title="Lead" roleLabel={role}>
        <div className="crm-panel"><p className="crm-error">{error}</p></div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout title={lead.name} roleLabel={role}>
      <div className="crm-panel">
        <div className="crm-detail-header">
          <Link to="/leads" className="crm-link crm-link-left">← All leads</Link>
          <div className="crm-inline-actions">
            {canEdit && lead.status !== "converted" && (
              <Link to={`/leads/${id}/edit`} className="crm-btn crm-btn-sm crm-btn-outline">Edit</Link>
            )}
            {canCreateDeal && lead.status !== "converted" && (
              <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={handleCreateDeal}>
                Create deal
              </button>
            )}
            {canCreateQuote && (
              <Link to={`/quotations/new?lead_id=${id}`} className="crm-btn crm-btn-sm crm-btn-outline">
                Create quotation
              </Link>
            )}
            {canEdit && !lead.contact_id && (
              <button type="button" className="crm-btn crm-btn-sm" onClick={handleConvert}>
                Convert to contact
              </button>
            )}
          </div>
        </div>

        {message && <p className="crm-success crm-mt">{message}</p>}
        {error && <p className="crm-error crm-mt">{error}</p>}

        <div className="crm-entity-status">
          <span className={`crm-badge crm-lead-${lead.status}`}>
            {STATUS_LABELS[lead.status] || lead.status}
          </span>
          {lead.csv_status && (
            <span className="crm-meta-sub">Original: {lead.csv_status}</span>
          )}
        </div>

        <dl className="crm-meta-grid">
          <div className="crm-meta-item">
            <dt>Phone</dt>
            <dd>{lead.phone || "—"}</dd>
          </div>
          <div className="crm-meta-item">
            <dt>Email</dt>
            <dd>{lead.email || "—"}</dd>
          </div>
          <div className="crm-meta-item">
            <dt>Organization</dt>
            <dd>{lead.organization_name || "—"}</dd>
          </div>
          <div className="crm-meta-item">
            <dt>City</dt>
            <dd>{lead.city || "—"}</dd>
          </div>
          <div className="crm-meta-item">
            <dt>Source</dt>
            <dd>{lead.source}</dd>
          </div>
          <div className="crm-meta-item">
            <dt>Assigned to</dt>
            <dd>{lead.assigned_to_name || "Unassigned"}</dd>
          </div>
          {lead.requirement && (
            <div className="crm-meta-item">
              <dt>Requirement</dt>
              <dd>{lead.requirement}</dd>
            </div>
          )}
          {lead.exact_requirement && (
            <div className="crm-meta-item">
              <dt>Exact requirement</dt>
              <dd>{lead.exact_requirement}</dd>
            </div>
          )}
          {lead.registered_at && (
            <div className="crm-meta-item">
              <dt>Registered</dt>
              <dd>{new Date(lead.registered_at).toLocaleDateString()}</dd>
            </div>
          )}
          {lead.contact_id && (
            <div className="crm-meta-item">
              <dt>Contact</dt>
              <dd>
                <Link to={`/contacts/${lead.contact_id}`} className="crm-nav-link">
                  View client #{lead.contact_id}
                </Link>
              </dd>
            </div>
          )}
        </dl>

        {lead.notes && (
          <div className="crm-entity-section">
            <h3>Legacy notes</h3>
            <pre className="crm-pre">{lead.notes}</pre>
          </div>
        )}

        {hasPermission("reminders.view") && (
          <RemindersPanel leadId={Number(id)} contactId={lead.contact_id || undefined} compact />
        )}

        {hasPermission("client_notes.view") && (
          <ClientNotesPanel
            leadId={Number(id)}
            contactName={lead.name}
            compact
          />
        )}

        {(hasPermission("files.view") || hasPermission("files.view_own")) && (
          <DocumentsPanel leadId={Number(id)} />
        )}
      </div>
    </DashboardLayout>
  );
}


export default LeadDetail;
