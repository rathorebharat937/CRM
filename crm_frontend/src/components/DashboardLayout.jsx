import { useEffect, useState, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { 
  Search, PanelLeftClose, PanelLeft, Plus, Bell, MessageSquare, LogOut, 
  ChevronDown, ChevronRight, Star, Settings, Shield, User, Globe, ShoppingBag, 
  Terminal, Activity, Clock, Briefcase, FileText, CheckSquare, Users, CreditCard,
  BookOpen, HelpCircle, Laptop, Layers, ClipboardList, TrendingUp
} from "lucide-react";

import { API_URL, apiFetch, clearSession, getAuthHeaders } from "../utils/api";
import { getPermissions, setPermissions, hasPermission } from "../utils/permissions";
import { getRoleHomePath, getRoleLabel, isRoleHomePath } from "../utils/roleHome";
import { CRM_APPS, filterAppsByPermission } from "../config/appCatalog";
import NotificationBell from "./NotificationBell";

// Map category IDs to headers
const CATEGORIES_LABELS = {
  sales: "CRM & Sales",
  billing: "Billing & GST",
  people: "HR & Team",
  finance: "Finance & Accounts",
  inventory: "Inventory & Stock",
  operations: "Projects & Operations",
  platform: "Platform & Growth",
  admin: "Administration",
};

// Map app icons to Lucide components
const ICON_MAP = {
  leads: Users,
  pipeline: TrendingUp,
  followups: Clock,
  contacts: Users,
  notes: FileText,
  quotations: FileText,
  invoices: CreditCard,
  payments: CreditCard,
  tax: Layers,
  ledger: BookOpen,
  orders: ClipboardList,
  projects: Briefcase,
  products: Layers,
  documents: FileText,
  marketing: Globe,
  website: Laptop,
  shop: ShoppingBag,
  pos: Laptop,
  manufacturing: Settings,
  quality: Shield,
  maintenance: Settings,
  fieldService: Layers,
  subscription: CreditCard,
  rental: Layers,
  aiSpark: Terminal,
  workflow: Settings,
  marketplace: Globe,
  employees: Users,
  attendance: CheckSquare,
  leave: Clock,
  timesheets: Clock,
  payroll: CreditCard,
  recruitment: Users,
  expenses: CreditCard,
  vendorBills: CreditCard,
  purchase: ClipboardList,
  reports: Layers,
  inventory: Layers,
  stock: Layers,
  warehouse: Layers,
  approvals: Shield,
  chat: MessageSquare,
  users: Users,
  company: Settings,
  branding: Layers,
  activity: Activity,
  alerts: Bell,
  email: FileText,
  settings: Settings,
  numbering: Terminal,
  roles: Shield,
};

function DashboardLayout({ title, roleLabel, children }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const role = localStorage.getItem("role");
  const homePath = getRoleHomePath(role);
  const isHome = isRoleHomePath(pathname);
  const displayRole = roleLabel || getRoleLabel(role);
  const userName = localStorage.getItem("name");

  // Sidebar collapsible state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    localStorage.getItem("sidebarCollapsed") === "true"
  );

  // Collapsible category sections
  const [collapsedCats, setCollapsedCats] = useState(() => {
    try {
      const saved = localStorage.getItem("collapsedCategories");
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  // Favorites & Pinned items
  const [favorites, setFavorites] = useState(() => {
    try {
      const saved = localStorage.getItem("crmFavorites");
      return saved ? JSON.parse(saved) : ["leads", "invoices", "projects"];
    } catch {
      return ["leads", "invoices", "projects"];
    }
  });

  // Search Modal state
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const searchInputRef = useRef(null);

  // Quick Create dropdown state
  const [isQuickCreateOpen, setIsQuickCreateOpen] = useState(false);

  // Recent activity logs
  const [activities, setActivities] = useState([]);

  // Fetch permissions and logs
  useEffect(() => {
    if (localStorage.getItem("token") && getPermissions().length === 0) {
      apiFetch("/users/me/permissions")
        .then((data) => setPermissions(data.permissions))
        .catch(() => {});
    }

    // Load recent logs for the Activity panel
    apiFetch("/admin/activity-logs?limit=6")
      .then((data) => {
        if (data && data.items) {
          setActivities(data.items);
        }
      })
      .catch(() => {
        // Fallback to high-quality mockup activity logs if not admin/unauthorized
        setActivities([
          {
            id: 1,
            action: "lead_created",
            email: "Sarah L.",
            details: "New Lead: TechCorp Solutions added",
            created_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
            ip_address: "192.168.1.1",
          },
          {
            id: 2,
            action: "invoice_created",
            email: "Admin User",
            details: "Invoice #INV-2024-105 created for Acme Industries",
            created_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
            ip_address: "192.168.1.5",
          },
          {
            id: 3,
            action: "lead_converted",
            email: "Sales Agent",
            details: "Deal Closed: Global Logistics contract signed",
            created_at: new Date(Date.now() - 120 * 60 * 1000).toISOString(),
            ip_address: "192.168.1.8",
          },
        ]);
      });

    // Storage event listener for favorites updates
    const handleStorage = () => {
      try {
        const saved = localStorage.getItem("crmFavorites");
        if (saved) {
          setFavorites(JSON.parse(saved));
        }
      } catch {}
    };
    window.addEventListener("storage", handleStorage);
    return () => {
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  // Keyboard shortcut listener (Ctrl+K or Cmd+K)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setIsSearchOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Sync states to local storage
  const toggleSidebar = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem("sidebarCollapsed", String(next));
      return next;
    });
  };

  const toggleCategory = (catId) => {
    setCollapsedCats((prev) => {
      const next = { ...prev, [catId]: !prev[catId] };
      localStorage.setItem("collapsedCategories", JSON.stringify(next));
      return next;
    });
  };

  const toggleFavorite = (e, appId) => {
    e.preventDefault();
    e.stopPropagation();
    setFavorites((prev) => {
      const next = prev.includes(appId)
        ? prev.filter((id) => id !== appId)
        : [...prev, appId];
      localStorage.setItem("crmFavorites", JSON.stringify(next));
      return next;
    });
  };

  const handleLogout = async () => {
    try {
      await fetch(`${API_URL}/logout`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
    } catch {
      // still clear local session
    }
    clearSession();
    navigate("/");
  };

  // Filter apps in sidebar by permissions
  const allowedApps = filterAppsByPermission(CRM_APPS, hasPermission);

  // Group apps by category
  const appsByCategory = allowedApps.reduce((acc, app) => {
    const cat = app.category || "platform";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(app);
    return acc;
  }, {});

  // Favorites list mapped from allowed apps
  const favoriteApps = allowedApps.filter((app) => favorites.includes(app.id));

  // Search filter
  const searchResults = searchQuery.trim()
    ? allowedApps.filter(
        (app) =>
          app.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
          app.subtitle?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : [];

  return (
    <div className="crm-layout-container">
      {/* LEFT COLLAPSIBLE SIDEBAR */}
      <aside className={`crm-premium-sidebar${sidebarCollapsed ? " collapsed" : ""}`}>
        <div className="crm-sidebar-header">
          <Link to={homePath} className="crm-sidebar-logo-wrap">
            <img src="/branding/logo.svg" alt="BlackPapers logo" className="crm-sidebar-logo" />
            {!sidebarCollapsed && <span>BlackPapers</span>}
          </Link>
          <button onClick={toggleSidebar} className="crm-sidebar-toggle" title="Toggle Sidebar">
            {sidebarCollapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
          </button>
        </div>

        {/* Global Search Button in Sidebar */}
        <button className="crm-sidebar-search-btn" onClick={() => setIsSearchOpen(true)}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Search size={15} />
            {!sidebarCollapsed && <span>Search modules...</span>}
          </div>
          {!sidebarCollapsed && <span className="crm-kbd">⌘K</span>}
        </button>

        {/* Sidebar Navigation items */}
        <div className="crm-sidebar-scroll">
          {/* Favorites Section */}
          {!sidebarCollapsed && favoriteApps.length > 0 && (
            <div className="crm-sidebar-section">
              <div className="crm-sidebar-section-header">
                <span>Favorites</span>
                <Star size={12} fill="#F59E0B" color="#F59E0B" />
              </div>
              <div className="crm-sidebar-items">
                {favoriteApps.map((app) => {
                  const IconComp = ICON_MAP[app.icon] || FileText;
                  const isActive = pathname === app.path;
                  return (
                    <Link
                      key={app.id}
                      to={app.path}
                      className={`crm-sidebar-link${isActive ? " active" : ""}`}
                    >
                      <span className="crm-sidebar-link-icon" style={{ color: app.color }}>
                        <IconComp size={16} />
                      </span>
                      <span>{app.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}

          {/* Module Categories */}
          {Object.entries(CATEGORIES_LABELS).map(([catId, label]) => {
            const apps = appsByCategory[catId] || [];
            if (apps.length === 0) return null;
            const isCollapsed = collapsedCats[catId];

            return (
              <div key={catId} className="crm-sidebar-section">
                {!sidebarCollapsed ? (
                  <div className="crm-sidebar-section-header" onClick={() => toggleCategory(catId)}>
                    <span>{label}</span>
                    {isCollapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
                  </div>
                ) : (
                  <div style={{ height: "1px", background: "rgba(255,255,255,0.05)", margin: "8px 0" }} />
                )}

                {(!isCollapsed || sidebarCollapsed) && (
                  <div className="crm-sidebar-items">
                    {apps.map((app) => {
                      const IconComp = ICON_MAP[app.icon] || FileText;
                      const isActive = pathname === app.path;
                      return (
                        <Link
                          key={app.id}
                          to={app.path}
                          className={`crm-sidebar-link${isActive ? " active" : ""}`}
                          title={sidebarCollapsed ? app.label : app.subtitle}
                        >
                          <span className="crm-sidebar-link-icon" style={{ color: app.color }}>
                            <IconComp size={16} />
                          </span>
                          {!sidebarCollapsed && <span>{app.label}</span>}
                          {!sidebarCollapsed && (
                            <button
                              onClick={(e) => toggleFavorite(e, app.id)}
                              className={`crm-app-tile-favorite${favorites.includes(app.id) ? " active" : ""}`}
                              style={{ marginLeft: "auto" }}
                            >
                              <Star size={12} fill={favorites.includes(app.id) ? "#F59E0B" : "transparent"} />
                            </button>
                          )}
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Sidebar Footer - User Profile Summary */}
        <div className="crm-sidebar-footer">
          <div className="crm-sidebar-user-avatar">
            {(userName || displayRole).charAt(0).toUpperCase()}
          </div>
          {!sidebarCollapsed && (
            <div className="crm-sidebar-user-info">
              <span className="crm-sidebar-user-name">{userName || "Profile"}</span>
              <span className="crm-sidebar-user-role">{displayRole}</span>
            </div>
          )}
        </div>
      </aside>

      {/* MAIN WRAPPER */}
      <div className="crm-layout-main">
        {/* STICKY TOP HEADER */}
        <header className="crm-premium-header">
          <div className="crm-header-left">
            <nav className="crm-header-breadcrumb" aria-label="Breadcrumb">
              <Link to={homePath}>Workspace</Link>
              {!isHome && (
                <>
                  <span className="crm-header-breadcrumb-separator">/</span>
                  <span>{title}</span>
                </>
              )}
            </nav>
          </div>

          <div className="crm-header-right">
            {/* Instant Search input (triggers modal) */}
            <div className="crm-search-trigger" onClick={() => setIsSearchOpen(true)}>
              <Search size={15} />
              <span>Search modules... (⌘K)</span>
            </div>

            {/* Quick Actions Dropdown */}
            <div style={{ position: "relative" }}>
              <button 
                className="crm-quick-create-btn"
                onClick={() => setIsQuickCreateOpen(!isQuickCreateOpen)}
              >
                <Plus size={16} />
                <span>Quick Create</span>
                <ChevronDown size={14} />
              </button>
              {isQuickCreateOpen && (
                <>
                  <div 
                    style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, zIndex: 110 }} 
                    onClick={() => setIsQuickCreateOpen(false)}
                  />
                  <div className="crm-notification-dropdown" style={{ display: "block", right: 0, top: "calc(100% + 8px)", zIndex: 120, width: "200px" }}>
                    <div style={{ padding: "8px 0" }}>
                      <Link to="/leads/new" className="crm-notification-item" style={{ padding: "8px 16px" }} onClick={() => setIsQuickCreateOpen(false)}>+ New Lead</Link>
                      <Link to="/invoices/new" className="crm-notification-item" style={{ padding: "8px 16px" }} onClick={() => setIsQuickCreateOpen(false)}>+ Create Invoice</Link>
                      <Link to="/contacts/new" className="crm-notification-item" style={{ padding: "8px 16px" }} onClick={() => setIsQuickCreateOpen(false)}>+ Create Customer</Link>
                      <Link to="/projects/new" className="crm-notification-item" style={{ padding: "8px 16px" }} onClick={() => setIsQuickCreateOpen(false)}>+ New Project</Link>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Custom notifications bell */}
            <NotificationBell />

            {/* Profile and log out */}
            <Link to="/profile" className="crm-header-icon-btn" title="View Profile">
              <User size={18} />
            </Link>
            
            <button
              onClick={handleLogout}
              className="crm-header-icon-btn"
              title="Log out"
              style={{ color: "var(--crm-danger)" }}
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>

        {/* CONTAINER BODY & COMPONENT RENDER */}
        <div className="crm-layout-main-scroll">
          <main className={`crm-layout-body${isHome ? " with-activity" : ""}`}>
            {children}

            {/* RIGHT SIDE ACTIVITY & NOTIFICATION PANEL */}
            {isHome && (
              <aside className="crm-activity-panel">
                <div className="crm-activity-section">
                  <h3 className="crm-activity-section-title">Recent Activity</h3>
                  <div className="crm-activity-list">
                    {activities.map((act) => (
                      <div key={act.id} className="crm-activity-item">
                        <span className="crm-activity-indicator success" />
                        <div className="crm-activity-content">
                          <span className="crm-activity-title">
                            {act.email ? `${act.email}: ` : ""}
                            {act.details}
                          </span>
                          <span className="crm-activity-time">
                            {new Date(act.created_at).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="crm-activity-section">
                  <h3 className="crm-activity-section-title">Notifications</h3>
                  <div className="crm-activity-list">
                    <div className="crm-activity-item">
                      <span className="crm-activity-indicator warning" />
                      <div className="crm-activity-content">
                        <span className="crm-activity-title">Weekly Report Ready</span>
                        <span className="crm-activity-desc">Q3 Sales Analysis is generated.</span>
                        <span className="crm-activity-time">1 day ago</span>
                      </div>
                    </div>
                    <div className="crm-activity-item">
                      <span className="crm-activity-indicator primary" />
                      <div className="crm-activity-content">
                        <span className="crm-activity-title">System Update Installed</span>
                        <span className="crm-activity-desc">New premium UI dashboard features enabled.</span>
                        <span className="crm-activity-time">2 days ago</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: "auto", paddingTop: "20px" }}>
                  <Link to="/help-support" style={{ fontSize: "0.8rem", color: "var(--crm-accent)", display: "flex", alignItems: "center", gap: "6px", textDecoration: "none", fontWeight: "600" }}>
                    <HelpCircle size={14} />
                    <span>Help & Support</span>
                  </Link>
                </div>
              </aside>
            )}
          </main>
        </div>
      </div>

      {/* GLOBAL SEARCH DIALOG OVERLAY */}
      {isSearchOpen && (
        <div className="crm-search-overlay" onClick={() => setIsSearchOpen(false)}>
          <div className="crm-search-modal" onClick={(e) => e.stopPropagation()}>
            <div className="crm-search-input-wrap">
              <Search size={18} color="var(--crm-muted)" />
              <input
                ref={searchInputRef}
                autoFocus
                placeholder="Search modules, records, and tools..."
                className="crm-search-modal-input"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <span className="crm-kbd">ESC</span>
            </div>
            
            <div className="crm-search-results">
              {searchQuery.trim() === "" ? (
                <>
                  <div className="crm-search-result-group-title">Suggestions</div>
                  {allowedApps.slice(0, 5).map((app) => (
                    <Link
                      key={app.id}
                      to={app.path}
                      onClick={() => setIsSearchOpen(false)}
                      className="crm-search-result-item"
                    >
                      <span style={{ color: app.color }}>●</span>
                      <span>{app.label}</span>
                      <span className="crm-search-result-sub">{app.subtitle}</span>
                    </Link>
                  ))}
                </>
              ) : searchResults.length > 0 ? (
                <>
                  <div className="crm-search-result-group-title">Matching Apps & Modules</div>
                  {searchResults.map((app) => (
                    <Link
                      key={app.id}
                      to={app.path}
                      onClick={() => setIsSearchOpen(false)}
                      className="crm-search-result-item"
                    >
                      <span style={{ color: app.color }}>●</span>
                      <span>{app.label}</span>
                      <span className="crm-search-result-sub">{app.subtitle}</span>
                    </Link>
                  ))}
                </>
              ) : (
                <div style={{ padding: "20px", textAlign: "center", color: "var(--crm-muted)" }}>
                  No results found for "{searchQuery}"
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DashboardLayout;
