import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";
import { CAMPAIGN_STATUS_LABELS, CAMPAIGN_TYPE_LABELS, formatDateTime } from "../utils/marketing";
import { hasPermission } from "../utils/permissions";

function MarketingCampaignDetail() {
  const { id } = useParams();
  const role = localStorage.getItem("role") || "Staff";
  const [campaign, setCampaign] = useState(null);
  const [enrollments, setEnrollments] = useState([]);
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");

  const load = () =>
    Promise.all([
      apiFetch(`/marketing/campaigns/${id}`),
      apiFetch(`/marketing/campaigns/${id}/enrollments`),
      apiFetch(`/marketing/campaigns/${id}/send-logs`),
    ]).then(([c, e, l]) => {
      setCampaign(c);
      setEnrollments(e);
      setLogs(l);
    });

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, [id]);

  const activate = async () => {
    try {
      await apiFetch(`/marketing/campaigns/${id}/activate`, { method: "POST" });
      load().catch((err) => setError(err.message));
    } catch (err) {
      setError(err.message);
    }
  };

  const pause = async () => {
    try {
      await apiFetch(`/marketing/campaigns/${id}/pause`, { method: "POST" });
      load().catch((err) => setError(err.message));
    } catch (err) {
      setError(err.message);
    }
  };

  if (!campaign) {
    return (
      <DashboardLayout title="Campaign" roleLabel={role}>
        <p className="crm-muted">Loading…</p>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout title={campaign.name} roleLabel={role}>
      <div className="crm-panel">
        <div className="crm-detail-header">
          <p className="crm-muted">
            {campaign.campaign_code} · {CAMPAIGN_TYPE_LABELS[campaign.campaign_type]} · {CAMPAIGN_STATUS_LABELS[campaign.status]}
          </p>
          <div className="crm-inline-actions">
            <Link to="/marketing" className="crm-btn crm-btn-sm crm-btn-outline">Back</Link>
            {hasPermission("marketing.activate") && campaign.status === "draft" && (
              <button type="button" className="crm-btn crm-btn-sm" onClick={activate}>Activate & enroll</button>
            )}
            {hasPermission("marketing.activate") && campaign.status === "active" && (
              <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={pause}>Pause</button>
            )}
          </div>
        </div>

        {error && <p className="crm-error crm-mt">{error}</p>}
        {campaign.description && <p className="crm-mt">{campaign.description}</p>}

        <section className="crm-mt">
          <h3>Steps ({campaign.steps_json.length})</h3>
          <ol className="crm-marketing-steps">
            {campaign.steps_json.map((step, idx) => (
              <li key={idx}>
                <strong>Day {step.delay_days}</strong> · {step.channel} — {step.subject}
                <p className="crm-muted">{step.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="crm-mt">
          <h3>Enrollments ({enrollments.length})</h3>
          <table className="crm-table">
            <thead>
              <tr><th>Lead / Contact</th><th>Status</th><th>Step</th><th>Next send</th></tr>
            </thead>
            <tbody>
              {enrollments.map((e) => (
                <tr key={e.id}>
                  <td>{e.lead_name || e.contact_name || "—"}</td>
                  <td>{e.status}</td>
                  <td>{e.current_step}</td>
                  <td>{formatDateTime(e.next_send_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="crm-mt">
          <h3>Recent sends</h3>
          <table className="crm-table">
            <thead>
              <tr><th>Step</th><th>Channel</th><th>Status</th><th>Subject</th><th>Sent</th></tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id}>
                  <td>{log.step_index + 1}</td>
                  <td>{log.channel}</td>
                  <td>{log.status}</td>
                  <td>{log.subject}</td>
                  <td>{formatDateTime(log.sent_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </DashboardLayout>
  );
}

export default MarketingCampaignDetail;
