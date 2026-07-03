import { useEffect, useState, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
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

// Categories Ordering and Mapping
const CATEGORY_ORDER = [
  "sales",      // CRM
  "billing",    // Finance
  "platform",   // Platform
  "people",     // HR
  "inventory",  // Inventory
  "operations", // Projects
  "finance",    // Reports
  "admin",      // Administration
];

const CATEGORIES_LABELS = {
  sales: "CRM",
  billing: "Finance",
  platform: "Platform",
  people: "HR",
  inventory: "Inventory",
  operations: "Projects",
  finance: "Reports",
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

  // Favorites / Pinned items
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

  // Sidebar search input state (filters list in-place)
  const [sidebarSearch, setSidebarSearch] = useState("");

  // Quick Create dropdown state
  const [isQuickCreateOpen, setIsQuickCreateOpen] = useState(false);

  // Fetch permissions
  useEffect(() => {
    if (localStorage.getItem("token") && getPermissions().length === 0) {
      apiFetch("/users/me/permissions")
        .then((data) => setPermissions(data.permissions))
        .catch(() => {});
    }
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

  // Listen to favorite updates from app tiles
  useEffect(() => {
    const handleStorage = () => {
      try {
        const saved = localStorage.getItem("crmFavorites");
        if (saved) setFavorites(JSON.parse(saved));
      } catch {}
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

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

  // Favorites list
  const favoriteApps = allowedApps.filter((app) => favorites.includes(app.id));

  // Search filter inside sidebar
  const getFilteredApps = (appsList) => {
    if (!sidebarSearch.trim()) return appsList;
    return appsList.filter((app) =>
      app.label.toLowerCase().includes(sidebarSearch.toLowerCase()) ||
      app.subtitle?.toLowerCase().includes(sidebarSearch.toLowerCase())
    );
  };

  // Search filter for top search overlay
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

        {/* Sidebar Inline Search Filter */}
        {!sidebarCollapsed ? (
          <div style={{ padding: "8px 14px", position: "relative" }}>
            <input
              type="text"
              placeholder="Search modules... (⌘K)"
              className="crm-sidebar-search-btn"
              style={{ width: "100%", margin: 0, paddingRight: "30px", cursor: "text" }}
              value={sidebarSearch}
              onChange={(e) => setSidebarSearch(e.target.value)}
            />
            {sidebarSearch && (
              <button 
                onClick={() => setSidebarSearch("")}
                style={{ position: "absolute", right: "22px", top: "16px", background: "transparent", border: "none", color: "var(--crm-muted)", fontSize: "0.8rem", cursor: "pointer" }}
              >
                ×
              </button>
            )}
          </div>
        ) : (
          <button className="crm-sidebar-search-btn" onClick={toggleSidebar} title="Search modules">
            <Search size={15} />
          </button>
        )}

        {/* Sidebar Navigation items */}
        <div className="crm-sidebar-scroll">
          {/* Main Dashboard home button */}
          <div className="crm-sidebar-items" style={{ marginBottom: "12px" }}>
            <Link
              to={homePath}
              className={`crm-sidebar-link${pathname === homePath ? " active" : ""}`}
            >
              <span className="crm-sidebar-link-icon" style={{ color: "var(--crm-accent)" }}>
                <Laptop size={16} />
              </span>
              {!sidebarCollapsed && <span>Dashboard</span>}
            </Link>
          </div>

          {/* Favorites / Pinned Section */}
          {!sidebarCollapsed && favoriteApps.length > 0 && !sidebarSearch.trim() && (
            <div className="crm-sidebar-section">
              <div className="crm-sidebar-section-header">
                <span>Pinned Favorites</span>
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

          {/* Module Categories (Dynamic loops over all CRM_APPS) */}
          {CATEGORY_ORDER.map((catId) => {
            const label = CATEGORIES_LABELS[catId];
            const rawApps = appsByCategory[catId] || [];
            const apps = getFilteredApps(rawApps);
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

                {(!isCollapsed || sidebarCollapsed || sidebarSearch.trim() !== "") && (
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

          {/* Help & Support Category */}
          <div className="crm-sidebar-section">
            {!sidebarCollapsed ? (
              <div className="crm-sidebar-section-header">
                <span>Support</span>
              </div>
            ) : (
              <div style={{ height: "1px", background: "rgba(255,255,255,0.05)", margin: "8px 0" }} />
            )}
            <div className="crm-sidebar-items">
              <Link to="/help-support" className="crm-sidebar-link" title="Help & Support">
                <span className="crm-sidebar-link-icon" style={{ color: "#38bdf8" }}>
                  <HelpCircle size={16} />
                </span>
                {!sidebarCollapsed && <span>Help & Support</span>}
              </Link>
            </div>
          </div>
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
              <Link to={homePath}>{displayRole} Workspace</Link>
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

            {/* Quick Create Dropdown */}
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

            {/* Current Portal Name Badge */}
            <span className="crm-shell-role-pill" style={{ textTransform: "capitalize", background: "rgba(124, 58, 237, 0.15)", borderColor: "rgba(124, 58, 237, 0.3)", color: "var(--crm-text)", fontSize: "0.8rem", padding: "6px 12px", borderRadius: "20px", fontWeight: "600" }}>
              {displayRole} Portal
            </span>

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
          <main className="crm-layout-body">
            {children}
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
