import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Plus, Play, Sparkles, TrendingUp, CheckSquare, Award } from "lucide-react";

import AppLauncher from "./AppLauncher";
import SalesKpis from "./SalesKpis";
import { apiFetch } from "../utils/api";

function RoleHomePage({
  greeting = "Welcome back",
  subtitle,
  children,
  showKpis = true,
  launcherTitle = "Your apps",
  launcherSubtitle,
}) {
  const [currentDate, setCurrentDate] = useState("");
  const [revenueVal, setRevenueVal] = useState("₹8,542,000");
  const [leadsCount, setLeadsCount] = useState("4,236");
  const [approvalsCount, setApprovalsCount] = useState("45");

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
      {/* PREMIUM DASHBOARD HERO */}
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

      {/* QUICK ACTIONS BAR */}
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

      {/* KPI CARDS (AT A GLANCE) */}
      {showKpis && (
        <motion.div variants={itemVariants}>
          <SalesKpis />
        </motion.div>
      )}

      {/* PERFORMANCE ANALYTICS SECTION */}
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

        {/* Premium SVG interactive line chart */}
        <div className="crm-svg-chart-container">
          <svg viewBox="0 0 800 200" width="100%" height="100%" preserveAspectRatio="none">
            <defs>
              <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--crm-primary)" stopOpacity="0.25" />
                <stop offset="100%" stopColor="var(--crm-primary)" stopOpacity="0" />
              </linearGradient>
            </defs>
            
            {/* Grid Lines */}
            <line x1="0" y1="50" x2="800" y2="50" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
            <line x1="0" y1="100" x2="800" y2="100" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
            <line x1="0" y1="150" x2="800" y2="150" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
            
            {/* Target Line (flat dash-array) */}
            <path
              d="M 0 130 Q 150 120 300 110 T 600 100 T 800 90"
              fill="none"
              stroke="#4B5563"
              strokeWidth="2"
              strokeDasharray="4 4"
              opacity="0.8"
            />
            
            {/* Revenue Gradient Fill */}
            <path
              d="M 0 170 Q 150 150 300 120 T 600 80 T 800 60 L 800 200 L 0 200 Z"
              fill="url(#chartGrad)"
            />
            
            {/* Revenue Line */}
            <path
              d="M 0 170 Q 150 150 300 120 T 600 80 T 800 60"
              fill="none"
              stroke="var(--crm-primary)"
              strokeWidth="3.5"
              strokeLinecap="round"
            />

            {/* Interactive node indicator */}
            <circle cx="600" cy="80" r="5" fill="var(--crm-primary)" />
            <circle cx="600" cy="80" r="10" fill="none" stroke="var(--crm-primary)" strokeWidth="2" opacity="0.5" />
          </svg>
          
          {/* Tooltip on the chart */}
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

      {/* RE-DESIGNED APP LAUNCHER */}
      <motion.div variants={itemVariants}>
        <AppLauncher
          title={launcherTitle}
          subtitle={launcherSubtitle}
          groupByCategory
          className="crm-role-home-launcher"
        />
      </motion.div>
    </motion.div>
  );
}

export default RoleHomePage;
