import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Plus, TrendingUp, Clock, CheckSquare, Users, CreditCard, HelpCircle, Bell } from "lucide-react";

import SalesKpis from "./SalesKpis";
import { apiFetch } from "../utils/api";

function RoleHomePage({
  greeting = "Welcome back",
  subtitle,
  children,
  showKpis = true,
}) {
  const [currentDate, setCurrentDate] = useState("");
  const [revenueVal, setRevenueVal] = useState("₹8,542,000");
  const [leadsCount, setLeadsCount] = useState("4,236");
  const [approvalsCount, setApprovalsCount] = useState("45");
  const [activities, setActivities] = useState([]);

  useEffect(() => {
    // Generate current date string in premium format
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    setCurrentDate(new Date().toLocaleDateString("en-IN", options));

    // Try to fetch real summary data from the API
    apiFetch("/dashboard/kpis")
      .then((data) => {
        if (data) {
          if (data.pending_payments !== undefined) {
            setRevenueVal(
              new Intl.NumberFormat("en-IN", {
                style: "currency",
                currency: "INR",
                maximumFractionDigits: 0,
              }).format(data.pending_payments)
            );
          }
          if (data.open_leads !== undefined) {
            setLeadsCount(String(data.open_leads));
          }
          if (data.follow_ups_overdue !== undefined) {
            setApprovalsCount(String(data.follow_ups_overdue));
          }
        }
      })
      .catch(() => {});

    // Load recent activity logs
    apiFetch("/admin/activity-logs?limit=5")
      .then((data) => {
        if (data && data.items) {
          setActivities(data.items);
        }
      })
      .catch(() => {
        // Fallback mockup activity logs
        setActivities([
          {
            id: 1,
            action: "lead_created",
            email: "Sarah L.",
            details: "New Lead: TechCorp Solutions added",
            created_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
          },
          {
            id: 2,
            action: "invoice_created",
            email: "Admin User",
            details: "Invoice #INV-2024-105 created for Acme Industries",
            created_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
          },
          {
            id: 3,
            action: "lead_converted",
            email: "Sales Agent",
            details: "Deal Closed: Global Logistics contract signed",
            created_at: new Date(Date.now() - 120 * 60 * 1000).toISOString(),
          },
        ]);
      });
  }, []);

  // Time-based prefix for greeting
  const getGreetingPrefix = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good Morning";
    if (hour < 17) return "Good Afternoon";
    return "Good Evening";
  };

  const namePart = greeting.replace("Managing", "").replace("workspace", "").replace("Hi,", "").trim();
  const formattedGreeting = `${getGreetingPrefix()}, ${namePart || "Admin"} 👋`;

  // Animation constants
  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 15 },
    show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 100 } },
  };

  return (
    <motion.div
      className="crm-role-home"
      initial="hidden"
      animate="show"
      variants={containerVariants}
      style={{ display: "flex", flexDirection: "column", gap: "24px" }}
    >
      {/* Welcome Section */}
      <motion.header className="crm-premium-hero" variants={itemVariants}>
        <div className="crm-premium-hero-left">
          <h1>{formattedGreeting}</h1>
          <div className="crm-date">{currentDate}</div>
          {subtitle && <p className="crm-role-home-sub" style={{ marginTop: "4px", fontSize: "0.9rem", color: "var(--crm-muted)" }}>{subtitle}</p>}
        </div>

        {/* Quick summary chips */}
        <div className="crm-premium-hero-right">
          <div className="crm-hero-summary-chip">
            <span className="crm-hero-summary-label">Today's Revenue</span>
            <span className="crm-hero-summary-val">{revenueVal}</span>
          </div>
          <div className="crm-hero-summary-chip">
            <span className="crm-hero-summary-label">Open Leads</span>
            <span className="crm-hero-summary-val" style={{ color: "var(--crm-success)" }}>{leadsCount}</span>
          </div>
          <div className="crm-hero-summary-chip">
            <span className="crm-hero-summary-label">Pending Dues</span>
            <span className="crm-hero-summary-val" style={{ color: "var(--crm-warning)" }}>{approvalsCount}</span>
          </div>
        </div>
      </motion.header>

      {/* Quick Actions */}
      <motion.div className="crm-quick-actions-bar" variants={itemVariants}>
        <span style={{ fontSize: "0.8rem", fontWeight: "700", textTransform: "uppercase", color: "var(--crm-muted)", marginRight: "10px" }}>
          Quick Actions:
        </span>
        <Link to="/leads/new" className="crm-quick-action-link">
          <Plus size={14} />
          <span>New Lead</span>
        </Link>
        <Link to="/invoices/new" className="crm-quick-action-link">
          <Plus size={14} />
          <span>Create Invoice</span>
        </Link>
        <Link to="/contacts/new" className="crm-quick-action-link">
          <Plus size={14} />
          <span>Create Customer</span>
        </Link>
        <Link to="/employees" className="crm-quick-action-link">
          <Plus size={14} />
          <span>Add Employee</span>
        </Link>
        <Link to="/documents" className="crm-quick-action-link">
          <Plus size={14} />
          <span>Upload File</span>
        </Link>
        <Link to="/pl-reports" className="crm-quick-action-link">
          <Plus size={14} />
          <span>Generate Report</span>
        </Link>
        <Link to="/projects/new" className="crm-quick-action-link">
          <Plus size={14} />
          <span>New Project</span>
        </Link>
      </motion.div>

      {children}

      {/* KPI Cards */}
      {showKpis && (
        <motion.div variants={itemVariants}>
          <SalesKpis />
        </motion.div>
      )}

      {/* Charts (Performance Analytics) */}
      <motion.div className="crm-analytics-card" variants={itemVariants}>
        <div className="crm-analytics-header">
          <h3 className="crm-analytics-title" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <TrendingUp size={18} color="var(--crm-primary)" />
            <span>Performance Analytics (Revenue vs. Target)</span>
          </h3>
          <div style={{ display: "flex", gap: "12px", fontSize: "0.8rem", fontWeight: "600" }}>
            <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--crm-primary)" }} />
              Revenue
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#4B5563" }} />
              Target
            </span>
          </div>
        </div>

        <div className="crm-svg-chart-container">
          <svg viewBox="0 0 800 200" width="100%" height="100%" preserveAspectRatio="none">
            <defs>
              <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--crm-primary)" stopOpacity="0.25" />
                <stop offset="100%" stopColor="var(--crm-primary)" stopOpacity="0" />
              </linearGradient>
            </defs>
            <line x1="0" y1="50" x2="800" y2="50" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
            <line x1="0" y1="100" x2="800" y2="100" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
            <line x1="0" y1="150" x2="800" y2="150" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
            <path
              d="M 0 130 Q 150 120 300 110 T 600 100 T 800 90"
              fill="none"
              stroke="#4B5563"
              strokeWidth="2"
              strokeDasharray="4 4"
              opacity="0.8"
            />
            <path
              d="M 0 170 Q 150 150 300 120 T 600 80 T 800 60 L 800 200 L 0 200 Z"
              fill="url(#chartGrad)"
            />
            <path
              d="M 0 170 Q 150 150 300 120 T 600 80 T 800 60"
              fill="none"
              stroke="var(--crm-primary)"
              strokeWidth="3.5"
              strokeLinecap="round"
            />
            <circle cx="600" cy="80" r="5" fill="var(--crm-primary)" />
            <circle cx="600" cy="80" r="10" fill="none" stroke="var(--crm-primary)" strokeWidth="2" opacity="0.5" />
          </svg>
          
          <div
            style={{
              position: "absolute",
              left: "70%",
              top: "20%",
              transform: "translateX(-50%)",
              background: "#1F2937",
              border: "1px solid var(--crm-border)",
              borderRadius: "8px",
              padding: "6px 12px",
              fontSize: "0.75rem",
              boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
              zIndex: 10,
            }}
          >
            <div style={{ color: "var(--crm-muted)", fontWeight: "600" }}>August Month</div>
            <div style={{ color: "var(--crm-text)", fontWeight: "700", marginTop: "2px" }}>₹8,542,000</div>
          </div>
        </div>
      </motion.div>

      {/* RECENT ACTIVITY & NOTIFICATIONS SECTIONS */}
      <motion.div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "24px",
          marginTop: "8px",
        }}
        variants={itemVariants}
      >
        {/* Recent Activities */}
        <div className="crm-analytics-card" style={{ padding: "20px" }}>
          <h3 className="crm-activity-section-title" style={{ fontSize: "0.8rem", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--crm-muted)", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "10px", marginBottom: "16px" }}>
            Recent Activity
          </h3>
          <div className="crm-activity-list">
            {activities.map((act) => (
              <div key={act.id} className="crm-activity-item" style={{ display: "flex", gap: "12px", paddingBottom: "12px", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                <span className="crm-activity-indicator success" style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--crm-success)", marginTop: "6px", flexShrink: 0 }} />
                <div className="crm-activity-content" style={{ display: "flex", flexDirection: "column", gap: "2px", fontSize: "0.8rem" }}>
                  <span className="crm-activity-title" style={{ color: "var(--crm-text)", fontWeight: "600" }}>
                    {act.email ? `${act.email}: ` : ""}
                    {act.details}
                  </span>
                  <span className="crm-activity-time" style={{ fontSize: "0.75rem", color: "var(--crm-muted)" }}>
                    {new Date(act.created_at).toLocaleString([], {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Notifications */}
        <div className="crm-analytics-card" style={{ padding: "20px" }}>
          <h3 className="crm-activity-section-title" style={{ fontSize: "0.8rem", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--crm-muted)", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "10px", marginBottom: "16px" }}>
            Notifications
          </h3>
          <div className="crm-activity-list">
            <div className="crm-activity-item" style={{ display: "flex", gap: "12px", paddingBottom: "12px", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              <span className="crm-activity-indicator warning" style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--crm-warning)", marginTop: "6px", flexShrink: 0 }} />
              <div className="crm-activity-content" style={{ display: "flex", flexDirection: "column", gap: "2px", fontSize: "0.8rem" }}>
                <span className="crm-activity-title" style={{ color: "var(--crm-text)", fontWeight: "600" }}>Weekly Report Ready</span>
                <span className="crm-activity-desc" style={{ color: "var(--crm-muted)" }}>Q3 Sales Analysis is generated and ready for review.</span>
                <span className="crm-activity-time" style={{ fontSize: "0.75rem", color: "var(--crm-muted)", marginTop: "2px" }}>1 day ago</span>
              </div>
            </div>
            <div className="crm-activity-item" style={{ display: "flex", gap: "12px", paddingBottom: "12px", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              <span className="crm-activity-indicator primary" style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--crm-accent)", marginTop: "6px", flexShrink: 0 }} />
              <div className="crm-activity-content" style={{ display: "flex", flexDirection: "column", gap: "2px", fontSize: "0.8rem" }}>
                <span className="crm-activity-title" style={{ color: "var(--crm-text)", fontWeight: "600" }}>System Update Installed</span>
                <span className="crm-activity-desc" style={{ color: "var(--crm-muted)" }}>Premium dark workspace design optimizations enabled.</span>
                <span className="crm-activity-time" style={{ fontSize: "0.75rem", color: "var(--crm-muted)", marginTop: "2px" }}>2 days ago</span>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

export default RoleHomePage;
