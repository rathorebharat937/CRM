import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import {
  ActionStatusMessages,
  ModuleDisabledBanner,
  ModulePageHeader,
  ModuleSection,
} from "../components/ModulePage";
import { apiFetch } from "../utils/api";
import { CAMPAIGN_STATUS_LABELS, CAMPAIGN_TYPE_LABELS, formatDateTime } from "../utils/marketing";
import { hasPermission } from "../utils/permissions";

function MarketingHub() {
  const role = localStorage.getItem("role") || "Staff";
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [processing, setProcessing] = useState(false);

  const load = () =>
    Promise.all([
      apiFetch("/marketing/dashboard"),
      apiFetch("/marketing/campaigns?limit=100"),
      apiFetch("/marketing/templates"),
    ]).then(([dash, list, tpls]) => {
      setDashboard(dash);
      setCampaigns(list.items || []);
      setTemplates(tpls || []);
    });

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  const createFromTemplate = async (key) => {
    setError("");
    setSuccess("");
    try {
      const c = await apiFetch(`/marketing/templates/${key}`, { method: "POST" });
      navigate(`/marketing/campaigns/${c.id}`);
    } catch (err) {
      setError(err.message);
    }
  };

  const processDue = async () => {
    setProcessing(true);
    setError("");
    setSuccess("");
    try {
      const res = await apiFetch("/marketing/process-due", { method: "POST" });
      await load();
      setSuccess(`Processed ${res.processed} due enrollment step(s).`);
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <DashboardLayout title="Marketing Automation" roleLabel={role}>
      <div className="crm-panel">
        <ModulePageHeader subtitle="Drip campaigns, nurture flows, and reactivation journeys">
          {hasPermission("marketing.run") && (
            <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={processDue} disabled={processing}>
              {processing ? "Running…" : "Process due steps"}
            </button>
          )}
          {hasPermission("marketing.manage_settings") && (
            <Link to="/marketing/settings" className="crm-btn crm-btn-sm crm-btn-outline">Settings</Link>
          )}
        </ModulePageHeader>

        <ActionStatusMessages error={error} success={success} successText={success} />
        {dashboard && !dashboard.is_enabled && <ModuleDisabledBanner moduleName="Marketing Automation" />}

        {dashboard && (
          <div className="crm-stats-grid crm-mt">
            <div className="crm-stat-card"><span className="crm-stat-value">{dashboard.active_campaigns}</span><span className="crm-stat-label">Active campaigns</span></div>
            <div className="crm-stat-card"><span className="crm-stat-value">{dashboard.total_enrolled}</span><span className="crm-stat-label">Enrolled</span></div>
            <div className="crm-stat-card"><span className="crm-stat-value">{dashboard.sends_today}</span><span className="crm-stat-label">Sends today</span></div>
            <div className="crm-stat-card"><span className="crm-stat-value">{dashboard.due_now}</span><span className="crm-stat-label">Due now</span></div>
          </div>
        )}

        {templates.length > 0 && hasPermission("marketing.create") && (
          <ModuleSection title="Starter templates">
            <div className="crm-card-grid">
              {templates.map((t) => (
                <div key={t.key} className="crm-card">
                  <h4>{t.name}</h4>
                  <p>{t.description}</p>
                  <p>{CAMPAIGN_TYPE_LABELS[t.campaign_type] || t.campaign_type} · {t.steps_json.length} steps</p>
                  <button type="button" className="crm-btn crm-btn-sm" onClick={() => createFromTemplate(t.key)}>Use template</button>
                </div>
              ))}
            </div>
          </ModuleSection>
        )}

        <ModuleSection title="Campaigns">
          {campaigns.length === 0 ? (
            <p className="crm-muted">No campaigns yet.</p>
          ) : (
            <table className="crm-table crm-mt">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Enrolled</th>
                  <th>Sent</th>
                  <th>Activated</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => (
                  <tr key={c.id}>
                    <td>{c.campaign_code}</td>
                    <td>{c.name}</td>
                    <td>{CAMPAIGN_TYPE_LABELS[c.campaign_type] || c.campaign_type}</td>
                    <td>{CAMPAIGN_STATUS_LABELS[c.status] || c.status}</td>
                    <td>{c.enrolled_count}</td>
                    <td>{c.sent_count}</td>
                    <td>{formatDateTime(c.activated_at)}</td>
                    <td>
                      <Link to={`/marketing/campaigns/${c.id}`} className="crm-btn crm-btn-sm crm-btn-outline">Open</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </ModuleSection>
      </div>
    </DashboardLayout>
  );
}

export default MarketingHub;
