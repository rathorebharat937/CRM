import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiFetch } from "../utils/api";
import { hasPermission } from "../utils/permissions";

function formatCurrency(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value || 0);
}

function SalesKpis() {
  const [kpis, setKpis] = useState(null);

  useEffect(() => {
    if (hasPermission("dashboard.view")) {
      apiFetch("/dashboard/kpis").then(setKpis).catch(() => {});
    }
  }, []);

  if (!kpis || !hasPermission("dashboard.view")) return null;

  const cards = [];

  if (hasPermission("leads.view")) {
    cards.push(
      <div key="leads" className="crm-stat-card">
        <p className="crm-stat-label">Open leads</p>
        <p className="crm-stat-value">{kpis.open_leads}</p>
        <p className="crm-muted">{kpis.total_leads} total</p>
        <Link to="/leads" className="crm-nav-link">View leads</Link>
      </div>,
    );
  }

  if (hasPermission("payments.view")) {
    cards.push(
      <div key="payments" className="crm-stat-card">
        <p className="crm-stat-label">Pending payments</p>
        <p className="crm-stat-value">{formatCurrency(kpis.pending_payments)}</p>
        <Link to="/payments" className="crm-nav-link">Collections</Link>
      </div>,
    );
  }

  if (hasPermission("reminders.view")) {
    cards.push(
      <div key="followups" className="crm-stat-card">
        <p className="crm-stat-label">Follow-ups overdue</p>
        <p className="crm-stat-value">{kpis.follow_ups_overdue}</p>
        <p className="crm-muted">{kpis.follow_ups_due_today} due today</p>
        <Link to="/follow-ups" className="crm-nav-link">Open queue</Link>
      </div>,
    );
  }

  if (hasPermission("projects.view")) {
    cards.push(
      <div key="tasks" className="crm-stat-card">
        <p className="crm-stat-label">Tasks this week</p>
        <p className="crm-stat-value">{kpis.tasks_due}</p>
        <p className="crm-muted">{kpis.tasks_overdue} overdue</p>
        <Link to="/projects/my-tasks" className="crm-nav-link">My tasks</Link>
      </div>,
    );
  }

  if (cards.length === 0) return null;

  return (
    <div className="crm-mt">
      <h3 className="crm-section-title">At a glance</h3>
      <div className="crm-stat-strip crm-mt-sm">{cards}</div>
    </div>
  );
}

export default SalesKpis;
