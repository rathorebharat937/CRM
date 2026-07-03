import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Users, CreditCard, Clock, CheckSquare, TrendingUp, TrendingDown } from "lucide-react";

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

  // Lead KPI card
  if (hasPermission("leads.view")) {
    cards.push(
      <div key="leads" className="crm-premium-kpi-card">
        <div className="crm-kpi-header">
          <span className="crm-kpi-title">Open Leads</span>
          <div className="crm-kpi-icon-wrap" style={{ color: "var(--crm-accent-secondary)" }}>
            <Users size={16} />
          </div>
        </div>
        <div className="crm-kpi-value-row">
          <span className="crm-kpi-value">{kpis.open_leads}</span>
          <span className="crm-kpi-trend down">
            <TrendingDown size={14} />
            <span>-3.2%</span>
          </span>
        </div>
        {/* Mini SVG Graph */}
        <div className="crm-kpi-chart">
          <svg viewBox="0 0 100 24" width="100%" height="100%" preserveAspectRatio="none">
            <path
              d="M0,18 Q15,22 30,12 T60,18 T90,24 T100,20"
              fill="none"
              stroke="var(--crm-danger)"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.75rem", marginTop: "2px" }}>
          <span className="crm-kpi-comparison">{kpis.total_leads} total leads</span>
          <Link to="/leads" style={{ color: "var(--crm-accent)", fontWeight: "600", textDecoration: "none" }}>View leads →</Link>
        </div>
      </div>
    );
  }

  // Payment KPI card
  if (hasPermission("payments.view")) {
    cards.push(
      <div key="payments" className="crm-premium-kpi-card">
        <div className="crm-kpi-header">
          <span className="crm-kpi-title">Pending Payments</span>
          <div className="crm-kpi-icon-wrap" style={{ color: "var(--crm-accent)" }}>
            <CreditCard size={16} />
          </div>
        </div>
        <div className="crm-kpi-value-row">
          <span className="crm-kpi-value">{formatCurrency(kpis.pending_payments)}</span>
          <span className="crm-kpi-trend up">
            <TrendingUp size={14} />
            <span>+12.5%</span>
          </span>
        </div>
        {/* Mini SVG Graph */}
        <div className="crm-kpi-chart">
          <svg viewBox="0 0 100 24" width="100%" height="100%" preserveAspectRatio="none">
            <path
              d="M0,20 Q20,12 40,16 T80,4 T100,2"
              fill="none"
              stroke="var(--crm-success)"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.75rem", marginTop: "2px" }}>
          <span className="crm-kpi-comparison">Outstanding dues</span>
          <Link to="/payments" style={{ color: "var(--crm-accent)", fontWeight: "600", textDecoration: "none" }}>Collections →</Link>
        </div>
      </div>
    );
  }

  // Follow Ups KPI card
  if (hasPermission("reminders.view")) {
    cards.push(
      <div key="followups" className="crm-premium-kpi-card">
        <div className="crm-kpi-header">
          <span className="crm-kpi-title">Follow-ups Overdue</span>
          <div className="crm-kpi-icon-wrap" style={{ color: "var(--crm-warning)" }}>
            <Clock size={16} />
          </div>
        </div>
        <div className="crm-kpi-value-row">
          <span className="crm-kpi-value">{kpis.follow_ups_overdue}</span>
          <span className="crm-kpi-trend up" style={{ color: "var(--crm-warning)" }}>
            <TrendingUp size={14} />
            <span>+5.1%</span>
          </span>
        </div>
        {/* Mini SVG Graph */}
        <div className="crm-kpi-chart">
          <svg viewBox="0 0 100 24" width="100%" height="100%" preserveAspectRatio="none">
            <path
              d="M0,18 Q20,10 40,14 T80,8 T100,10"
              fill="none"
              stroke="var(--crm-warning)"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.75rem", marginTop: "2px" }}>
          <span className="crm-kpi-comparison">{kpis.follow_ups_due_today} due today</span>
          <Link to="/follow-ups" style={{ color: "var(--crm-accent)", fontWeight: "600", textDecoration: "none" }}>Open queue →</Link>
        </div>
      </div>
    );
  }

  // Tasks KPI card
  if (hasPermission("projects.view")) {
    cards.push(
      <div key="tasks" className="crm-premium-kpi-card">
        <div className="crm-kpi-header">
          <span className="crm-kpi-title">Tasks This Week</span>
          <div className="crm-kpi-icon-wrap" style={{ color: "var(--crm-success)" }}>
            <CheckSquare size={16} />
          </div>
        </div>
        <div className="crm-kpi-value-row">
          <span className="crm-kpi-value">{kpis.tasks_due}</span>
          <span className="crm-kpi-trend down" style={{ color: "var(--crm-success)" }}>
            <TrendingDown size={14} />
            <span>-8.3%</span>
          </span>
        </div>
        {/* Mini SVG Graph */}
        <div className="crm-kpi-chart">
          <svg viewBox="0 0 100 24" width="100%" height="100%" preserveAspectRatio="none">
            <path
              d="M0,10 Q25,20 50,8 T80,12 T100,14"
              fill="none"
              stroke="var(--crm-success)"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.75rem", marginTop: "2px" }}>
          <span className="crm-kpi-comparison">{kpis.tasks_overdue} overdue tasks</span>
          <Link to="/projects/my-tasks" style={{ color: "var(--crm-accent)", fontWeight: "600", textDecoration: "none" }}>My tasks →</Link>
        </div>
      </div>
    );
  }

  if (cards.length === 0) return null;

  return (
    <div className="crm-mt">
      <h3 className="crm-section-title" style={{ fontSize: "0.85rem", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--crm-muted)", marginBottom: "12px" }}>
        At a glance
      </h3>
      <div className="crm-premium-kpi-grid">{cards}</div>
    </div>
  );
}

export default SalesKpis;
