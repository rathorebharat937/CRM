import { useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { API_URL, apiFetch, clearSession, getAuthHeaders } from "../utils/api";
import { getPermissions, setPermissions } from "../utils/permissions";
import { getRoleHomePath, getRoleLabel, isRoleHomePath } from "../utils/roleHome";
import NotificationBell from "./NotificationBell";

function DashboardLayout({ title, roleLabel, children }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const role = localStorage.getItem("role");
  const homePath = getRoleHomePath(role);
  const isHome = isRoleHomePath(pathname);
  const displayRole = roleLabel || getRoleLabel(role);
  const userName = localStorage.getItem("name");

  useEffect(() => {
    if (localStorage.getItem("token") && getPermissions().length === 0) {
      apiFetch("/users/me/permissions")
        .then((data) => setPermissions(data.permissions))
        .catch(() => {});
    }
  }, []);

  const handleLogout = async () => {
    try {
      await fetch(`${API_URL}/logout`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
    } catch {
      // still clear local session if API is unreachable
    }
    clearSession();
    navigate("/");
  };

  return (
    <div className={`crm-dashboard${isHome ? " crm-dashboard-home" : ""}`}>
      <header className="crm-shell-header">
        <Link to={homePath} className="crm-shell-brand" aria-label="Back to apps home">
          <img src="/branding/logo.svg" alt="" className="crm-shell-logo" />
          <span className="crm-shell-brand-text">BlackPapers</span>
        </Link>

        {!isHome && (
          <nav className="crm-shell-crumb" aria-label="Breadcrumb">
            <Link to={homePath} className="crm-shell-back" aria-label="Back to all apps">
              ←
            </Link>
            <Link to={homePath}>Apps</Link>
            <span className="crm-shell-crumb-sep" aria-hidden="true">
              ›
            </span>
            <span className="crm-shell-crumb-current">{title}</span>
          </nav>
        )}

        <div className="crm-shell-spacer" />

        <div className="crm-shell-actions">
          <span className="crm-shell-role-pill">{displayRole}</span>
          <Link
            to="/profile"
            className={`crm-shell-profile${pathname === "/profile" ? " crm-shell-profile-active" : ""}`}
            title="My profile"
          >
            <span className="crm-shell-avatar" aria-hidden="true">
              {(userName || displayRole).charAt(0).toUpperCase()}
            </span>
            <span className="crm-shell-profile-name">{userName || "Profile"}</span>
          </Link>
          <NotificationBell />
          <button
            type="button"
            className="crm-btn crm-btn-outline crm-btn-sm crm-shell-logout"
            onClick={handleLogout}
          >
            Logout
          </button>
        </div>
      </header>

      <main className={`crm-dashboard-main${isHome ? " crm-dashboard-main-wide" : ""}`}>
        {!isHome && (
          <Link to={homePath} className="crm-back-to-apps" aria-label="Back to all apps">
            <span className="crm-back-to-apps-icon" aria-hidden="true">←</span>
            <span>All apps</span>
          </Link>
        )}
        {children}
      </main>
    </div>
  );
}

export default DashboardLayout;
