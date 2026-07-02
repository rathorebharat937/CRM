import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";
import { hasPermission } from "../utils/permissions";
import { formatCurrency, formatDate, subscriptionStatusClass } from "../utils/subscriptions";

function SubscriptionsDashboard() {
  const role = localStorage.getItem("role") || "Staff";
  const [settings, setSettings] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [billingMsg, setBillingMsg] = useState("");

  const load = () =>
    Promise.all([
      apiFetch("/subscriptions/settings"),
      apiFetch("/subscriptions/dashboard"),
    ])
      .then(([cfg, dash]) => {
        setSettings(cfg);
        setData(dash);
        setError("");
      })
      .catch((err) => setError(err.message));

  useEffect(() => { load(); }, []);

  const runBilling = async () => {
    setBillingMsg("");
    try {
      const result = await apiFetch("/subscriptions/run-billing", { method: "POST" });
      setBillingMsg(`Billing run: ${result.invoices_created} invoice(s) created, ${result.skipped} skipped.`);
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <DashboardLayout title="Subscriptions" roleLabel={role}>
      <div className="crm-panel">
        <div className="crm-detail-header">
          <p className="crm-muted">Recurring plans, renewals, and auto billing</p>
          <div className="crm-inline-actions">
            {hasPermission("subscriptions.create") && (
              <Link to="/subscriptions/new" className="crm-btn crm-btn-sm">New subscription</Link>
            )}
            <Link to="/subscriptions/list" className="crm-btn crm-btn-sm crm-btn-outline">All subscriptions</Link>
            <Link to="/subscriptions/plans" className="crm-btn crm-btn-sm crm-btn-outline">Plans</Link>
            {hasPermission("subscriptions.manage_settings") && (
              <Link to="/subscriptions/settings" className="crm-btn crm-btn-sm crm-btn-outline">Settings</Link>
            )}
            {hasPermission("subscriptions.bill") && (
              <button type="button" className="crm-btn crm-btn-sm" onClick={runBilling}>Run billing</button>
            )}
          </div>
        </div>
        {error && <p className="crm-error crm-mt">{error}</p>}
        {settings && !settings.is_enabled && (
          <p className="crm-muted crm-mt">
            Subscriptions module is not enabled.{" "}
            {hasPermission("subscriptions.manage_settings") ? (
              <Link to="/subscriptions/settings">Enable it in Settings</Link>
            ) : (
              "Ask an admin to enable it in Settings."
            )}
          </p>
        )}
        {billingMsg && <p className="crm-success crm-mt">{billingMsg}</p>}
        {data && settings?.is_enabled && (
          <>
            <div className="crm-stats-grid crm-mt">
              <div className="crm-stat-card"><span className="crm-stat-value">{data.active_subscriptions}</span><span className="crm-stat-label">Active</span></div>
              <div className="crm-stat-card"><span className="crm-stat-value">{formatCurrency(data.mrr)}</span><span className="crm-stat-label">MRR</span></div>
              <div className="crm-stat-card"><span className="crm-stat-value">{data.renewals_due_7d}</span><span className="crm-stat-label">Renewals (7d)</span></div>
              <div className="crm-stat-card"><span className="crm-stat-value">{data.past_due_count}</span><span className="crm-stat-label">Past due</span></div>
              <div className="crm-stat-card"><span className="crm-stat-value">{data.new_mtd}</span><span className="crm-stat-label">New (MTD)</span></div>
              <div className="crm-stat-card"><span className="crm-stat-value">{data.cancelled_mtd}</span><span className="crm-stat-label">Cancelled (MTD)</span></div>
            </div>
            <h3 className="crm-mt">Renewals due this week</h3>
            {data.renewals_due.length === 0 ? (
              <p className="crm-muted">No renewals due in the next 7 days.</p>
            ) : (
              <table className="crm-table crm-mt">
                <thead><tr><th>SUB #</th><th>Contact</th><th>Plan</th><th>Next billing</th><th>MRR</th></tr></thead>
                <tbody>
                  {data.renewals_due.map((s) => (
                    <tr key={s.id}>
                      <td><Link to={`/subscriptions/${s.id}`}>{s.subscription_number}</Link></td>
                      <td>{s.contact_name}</td>
                      <td>{s.plan_name}</td>
                      <td>{formatDate(s.next_billing_date)}</td>
                      <td>{formatCurrency(s.mrr_contribution)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <h3 className="crm-mt">Past due</h3>
            {data.past_due.length === 0 ? (
              <p className="crm-muted">No past due subscriptions.</p>
            ) : (
              <table className="crm-table crm-mt">
                <thead><tr><th>SUB #</th><th>Contact</th><th>Plan</th><th>Status</th><th></th></tr></thead>
                <tbody>
                  {data.past_due.map((s) => (
                    <tr key={s.id}>
                      <td><Link to={`/subscriptions/${s.id}`}>{s.subscription_number}</Link></td>
                      <td>{s.contact_name}</td>
                      <td>{s.plan_name}</td>
                      <td><span className={subscriptionStatusClass(s.status)}>{s.status}</span></td>
                      <td><Link to={`/subscriptions/${s.id}`} className="crm-btn crm-btn-sm crm-btn-outline">Open</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {data.recently_cancelled.length > 0 && (
              <>
                <h3 className="crm-mt">Recently cancelled</h3>
                <table className="crm-table crm-mt">
                  <thead><tr><th>SUB #</th><th>Contact</th><th>Plan</th><th>Status</th></tr></thead>
                  <tbody>
                    {data.recently_cancelled.map((s) => (
                      <tr key={s.id}>
                        <td><Link to={`/subscriptions/${s.id}`}>{s.subscription_number}</Link></td>
                        <td>{s.contact_name}</td>
                        <td>{s.plan_name}</td>
                        <td><span className={subscriptionStatusClass(s.status)}>{s.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

export default SubscriptionsDashboard;
