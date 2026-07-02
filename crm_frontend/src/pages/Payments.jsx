import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";

function formatCurrency(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value || 0);
}

function Payments() {
  const role = localStorage.getItem("role") || "Staff";
  const [tab, setTab] = useState("payments");
  const [summary, setSummary] = useState(null);
  const [payments, setPayments] = useState({ items: [], total: 0 });
  const [outstanding, setOutstanding] = useState({ items: [], total: 0 });
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch("/payments/summary").then(setSummary).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (tab === "payments") {
      apiFetch("/payments?limit=50").then(setPayments).catch((err) => setError(err.message));
    } else {
      const params = tab === "overdue" ? "?overdue_only=true&limit=50" : "?limit=50";
      apiFetch(`/payments/outstanding${params}`).then(setOutstanding).catch((err) => setError(err.message));
    }
  }, [tab]);

  return (
    <DashboardLayout title="Payments" roleLabel={role}>
      <div className="crm-panel">
        {summary && (
          <div className="crm-stat-strip">
            <div className="crm-stat-card">
              <span className="crm-stat-label">Total received</span>
              <strong>{formatCurrency(summary.total_received)}</strong>
            </div>
            <div className="crm-stat-card">
              <span className="crm-stat-label">Outstanding</span>
              <strong>{formatCurrency(summary.total_outstanding)}</strong>
            </div>
            <div className="crm-stat-card">
              <span className="crm-stat-label">Open invoices</span>
              <strong>{summary.invoice_count_outstanding}</strong>
            </div>
            <div className="crm-stat-card">
              <span className="crm-stat-label">Overdue</span>
              <strong>{summary.invoice_count_overdue}</strong>
            </div>
          </div>
        )}

        {summary?.aging_buckets?.length > 0 && (
          <div className="crm-mt-lg">
            <h3>Ageing (outstanding)</h3>
            <div className="crm-stats-grid crm-mt-sm">
              {summary.aging_buckets.map((bucket) => (
                <div key={bucket.label} className="crm-stat-card">
                  <p className="crm-stat-label">{bucket.label}</p>
                  <p className="crm-stat-value">{formatCurrency(bucket.amount)}</p>
                  <p className="crm-muted">{bucket.count} invoice{bucket.count === 1 ? "" : "s"}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="crm-contacts-toolbar crm-mt">
          {["payments", "outstanding", "overdue"].map((t) => (
            <button
              key={t}
              type="button"
              className={`crm-btn crm-btn-sm ${tab === t ? "crm-btn-inline" : "crm-btn-outline"}`}
              onClick={() => setTab(t)}
            >
              {t === "payments" ? "All payments" : t === "outstanding" ? "Outstanding" : "Overdue only"}
            </button>
          ))}
        </div>

        {error && <p className="crm-error crm-mt">{error}</p>}

        {tab === "payments" && (
          <div className="crm-table-wrap crm-mt">
            <table className="crm-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Invoice</th>
                  <th>Client</th>
                  <th>Amount</th>
                  <th>Method</th>
                  <th>Recorded by</th>
                </tr>
              </thead>
              <tbody>
                {payments.items.length === 0 && (
                  <tr><td colSpan={6} className="crm-muted">No payments recorded yet.</td></tr>
                )}
                {payments.items.map((p) => (
                  <tr key={p.id}>
                    <td>{new Date(p.payment_date).toLocaleDateString()}</td>
                    <td>
                      <Link to={`/invoices/${p.invoice_id}`} className="crm-nav-link">
                        {p.invoice_number || p.invoice_title}
                      </Link>
                    </td>
                    <td>
                      {p.contact_id ? (
                        <Link to={`/customer-ledger/${p.contact_id}`} className="crm-nav-link">
                          {p.client_org || p.client_name || "—"}
                        </Link>
                      ) : (
                        p.client_org || p.client_name || "—"
                      )}
                    </td>
                    <td>{formatCurrency(p.amount)}</td>
                    <td>{p.payment_method}</td>
                    <td>{p.recorded_by_name || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tab !== "payments" && (
          <div className="crm-table-wrap crm-mt">
            <table className="crm-table">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Client</th>
                  <th>Outstanding</th>
                  <th>Due date</th>
                  <th>Age</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {outstanding.items.length === 0 && (
                  <tr><td colSpan={6} className="crm-muted">No outstanding invoices in this view.</td></tr>
                )}
                {outstanding.items.map((inv) => (
                  <tr key={inv.id}>
                    <td>{inv.invoice_number || inv.title}</td>
                    <td>
                      {inv.contact_id ? (
                        <Link to={`/customer-ledger/${inv.contact_id}`} className="crm-nav-link">
                          {inv.client_org || inv.client_name || "—"}
                        </Link>
                      ) : (
                        inv.client_org || inv.client_name || "—"
                      )}
                    </td>
                    <td>{formatCurrency(inv.outstanding_amount)}</td>
                    <td>{inv.due_date ? new Date(inv.due_date).toLocaleDateString() : "—"}</td>
                    <td>{inv.age_days != null ? `${inv.age_days}d` : "—"}</td>
                    <td>
                      <Link to={`/invoices/${inv.id}`} className="crm-nav-link">View</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

export default Payments;
