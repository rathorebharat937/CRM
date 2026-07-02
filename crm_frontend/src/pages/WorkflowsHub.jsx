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
import { hasPermission } from "../utils/permissions";
import { formatDateTime, MODULE_LABELS } from "../utils/workflows";

function WorkflowsHub() {
  const role = localStorage.getItem("role") || "Staff";
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [workflows, setWorkflows] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [error, setError] = useState("");

  const load = () => {
    Promise.all([
      apiFetch("/workflows/dashboard"),
      apiFetch("/workflows?limit=100"),
      apiFetch("/workflows/templates"),
    ])
      .then(([dash, list, tpls]) => {
        setDashboard(dash);
        setWorkflows(list.items || []);
        setTemplates(tpls || []);
      })
      .catch((err) => setError(err.message));
  };

  useEffect(() => {
    load();
  }, []);

  const duplicateTemplate = async (key) => {
    setError("");
    try {
      const wf = await apiFetch(`/workflows/templates/${key}`, { method: "POST" });
      navigate(`/workflows/${wf.id}/edit`);
    } catch (err) {
      setError(err.message);
    }
  };

  const toggleActive = async (wf) => {
    setError("");
    try {
      const path = wf.is_active ? "deactivate" : "activate";
      await apiFetch(`/workflows/${wf.id}/${path}`, { method: "POST" });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <DashboardLayout title="Workflow Builder" roleLabel={role}>
      <div className="crm-panel">
        <ModulePageHeader subtitle="Custom automations with triggers, conditions, and actions">
          <Link to="/workflows/runs" className="crm-btn crm-btn-sm crm-btn-outline">Run history</Link>
          {hasPermission("workflows.manage_settings") && (
            <Link to="/workflows/settings" className="crm-btn crm-btn-sm crm-btn-outline">Settings</Link>
          )}
          {hasPermission("workflows.create") && (
            <Link to="/workflows/new" className="crm-btn crm-btn-sm">New workflow</Link>
          )}
        </ModulePageHeader>

        <ActionStatusMessages error={error} />
        {dashboard && !dashboard.is_enabled && <ModuleDisabledBanner moduleName="Workflow Builder" />}

        {dashboard && (
          <div className="crm-stats-grid crm-mt">
            <div className="crm-stat-card"><span className="crm-stat-value">{dashboard.active_count}</span><span className="crm-stat-label">Active</span></div>
            <div className="crm-stat-card"><span className="crm-stat-value">{dashboard.runs_today}</span><span className="crm-stat-label">Runs today</span></div>
            <div className="crm-stat-card"><span className="crm-stat-value">{dashboard.failures_today}</span><span className="crm-stat-label">Failures today</span></div>
          </div>
        )}

        {hasPermission("workflows.create") && templates.length > 0 && (
          <ModuleSection title="Starter templates">
            <div className="crm-card-grid">
              {templates.map((t) => (
                <div key={t.key} className="crm-card">
                  <h4>{t.name}</h4>
                  <p>{t.description}</p>
                  <button type="button" className="crm-btn crm-btn-sm" onClick={() => duplicateTemplate(t.key)}>Use template</button>
                </div>
              ))}
            </div>
          </ModuleSection>
        )}

        <ModuleSection title="Workflows">
          {workflows.length === 0 ? (
            <p className="crm-muted">No workflows yet.</p>
          ) : (
            <table className="crm-table crm-mt">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Module</th>
                  <th>Trigger</th>
                  <th>Active</th>
                  <th>Runs</th>
                  <th>Last run</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {workflows.map((w) => (
                  <tr key={w.id}>
                    <td><Link to={`/workflows/${w.id}`}>{w.workflow_code}</Link></td>
                    <td>{w.name}</td>
                    <td>{MODULE_LABELS[w.module] || w.module}</td>
                    <td>{w.trigger_type}</td>
                    <td>{w.is_active ? "Yes" : "No"}</td>
                    <td>{w.run_count}</td>
                    <td>{formatDateTime(w.last_run_at)}</td>
                    <td>
                      {hasPermission("workflows.activate") && (
                        <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={() => toggleActive(w)}>
                          {w.is_active ? "Deactivate" : "Activate"}
                        </button>
                      )}
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

export default WorkflowsHub;
