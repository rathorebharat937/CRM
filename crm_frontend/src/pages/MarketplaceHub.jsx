import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import {
  ActionStatusMessages,
  ModuleDisabledBanner,
  ModulePageHeader,
  ModuleSection,
} from "../components/ModulePage";
import { apiFetch } from "../utils/api";
import { hasPermission } from "../utils/permissions";

function MarketplaceHub() {
  const role = localStorage.getItem("role") || "Staff";
  const [dashboard, setDashboard] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [apiKeys, setApiKeys] = useState([]);
  const [webhooks, setWebhooks] = useState([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [createdKey, setCreatedKey] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = () =>
    Promise.all([
      apiFetch("/marketplace/dashboard"),
      apiFetch("/marketplace/catalog"),
      hasPermission("marketplace.manage_keys") ? apiFetch("/marketplace/api-keys") : Promise.resolve([]),
      hasPermission("marketplace.manage_webhooks") ? apiFetch("/marketplace/webhooks") : Promise.resolve([]),
    ]).then(([dash, cat, keys, hooks]) => {
      setDashboard(dash);
      setCatalog(cat);
      setApiKeys(keys);
      setWebhooks(hooks);
    });

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  const install = async (id) => {
    setError("");
    setSuccess("");
    try {
      await apiFetch(`/marketplace/integrations/${id}/install`, {
        method: "POST",
        body: JSON.stringify({ config_json: { configured: true } }),
      });
      setSuccess("Integration installed.");
      load().catch((err) => setError(err.message));
    } catch (err) {
      setError(err.message);
    }
  };

  const uninstall = async (id) => {
    setError("");
    setSuccess("");
    try {
      await apiFetch(`/marketplace/integrations/${id}/uninstall`, { method: "POST" });
      setSuccess("Integration uninstalled.");
      load().catch((err) => setError(err.message));
    } catch (err) {
      setError(err.message);
    }
  };

  const createKey = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    try {
      const res = await apiFetch("/marketplace/api-keys", {
        method: "POST",
        body: JSON.stringify({ name: newKeyName || "API key", scopes_json: ["read:leads", "read:contacts"] }),
      });
      setCreatedKey(res.api_key);
      setNewKeyName("");
      setSuccess("API key created. Copy it now — it will not be shown again.");
      load().catch(() => {});
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <DashboardLayout title="API & App Marketplace" roleLabel={role}>
      <div className="crm-panel">
        <ModulePageHeader subtitle="Install integrations, issue API keys, and register webhooks">
          {hasPermission("marketplace.manage_settings") && (
            <Link to="/marketplace/settings" className="crm-btn crm-btn-sm crm-btn-outline">Settings</Link>
          )}
        </ModulePageHeader>

        <ActionStatusMessages error={error} success={success} successText={success} />
        {dashboard && !dashboard.is_enabled && <ModuleDisabledBanner moduleName="API Marketplace" />}

        {dashboard && (
          <div className="crm-stat-strip crm-mt">
            <div className="crm-stat-card">
              <span className="crm-stat-label">Installed</span>
              <span className="crm-stat-value">{dashboard.installed_count}</span>
            </div>
            <div className="crm-stat-card">
              <span className="crm-stat-label">API keys</span>
              <span className="crm-stat-value">{dashboard.api_key_count}</span>
            </div>
            <div className="crm-stat-card">
              <span className="crm-stat-label">Webhooks</span>
              <span className="crm-stat-value">{dashboard.active_webhooks}</span>
            </div>
          </div>
        )}

        <ModuleSection title="Integration catalog">
          {catalog.length === 0 ? (
            <p className="crm-muted">No integrations in catalog.</p>
          ) : (
            <div className="crm-card-grid">
              {catalog.map((item) => (
                <div key={item.integration_key} className="crm-card">
                  <h4>{item.name}</h4>
                  <p>{item.category}</p>
                  <p>{item.description}</p>
                  {item.installed ? (
                    <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={() => uninstall(item.integration_id)} disabled={!hasPermission("marketplace.install")}>
                      Uninstall
                    </button>
                  ) : (
                    <button type="button" className="crm-btn crm-btn-sm" onClick={() => install(item.integration_id)} disabled={!hasPermission("marketplace.install")}>
                      Install
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </ModuleSection>

        {hasPermission("marketplace.manage_keys") && (
          <ModuleSection title="API keys">
            {createdKey && <code className="crm-module-code">{createdKey}</code>}
            <form className="crm-inline-form crm-mt" onSubmit={createKey}>
              <input value={newKeyName} onChange={(e) => setNewKeyName(e.target.value)} placeholder="Key name" />
              <button type="submit" className="crm-btn crm-btn-sm crm-btn-inline">Create key</button>
            </form>
            <table className="crm-table crm-mt">
              <thead><tr><th>Name</th><th>Prefix</th><th>Scopes</th><th>Active</th></tr></thead>
              <tbody>
                {apiKeys.map((k) => (
                  <tr key={k.id}><td>{k.name}</td><td>{k.key_prefix}…</td><td>{(k.scopes_json || []).join(", ")}</td><td>{k.is_active ? "Yes" : "No"}</td></tr>
                ))}
              </tbody>
            </table>
          </ModuleSection>
        )}

        {hasPermission("marketplace.manage_webhooks") && webhooks.length > 0 && (
          <ModuleSection title="Webhooks">
            <table className="crm-table">
              <thead><tr><th>Name</th><th>URL</th><th>Events</th><th>Status</th></tr></thead>
              <tbody>
                {webhooks.map((w) => (
                  <tr key={w.id}>
                    <td>{w.name}</td>
                    <td>{w.endpoint_url}</td>
                    <td>{(w.events_json || []).join(", ")}</td>
                    <td>{w.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ModuleSection>
        )}
      </div>
    </DashboardLayout>
  );
}

export default MarketplaceHub;
