import { useEffect, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { API_URL, apiFetch, clearSession, getAuthHeaders } from "../utils/api";
import { getPermissions, hasPermission, setPermissions } from "../utils/permissions";
import NotificationBell from "./NotificationBell";

function isNavActive(pathname, to) {
  switch (to) {
    case "/profile":
      return pathname === "/profile";
    case "/leads":
      return pathname === "/leads" || pathname.startsWith("/leads/");
    case "/pipeline":
      return pathname === "/pipeline" || pathname === "/deals" || pathname.startsWith("/deals/");
    case "/follow-ups":
      return pathname === "/follow-ups" || pathname.startsWith("/follow-ups/") || pathname === "/client-notes/follow-ups";
    case "/quotations":
      return pathname === "/quotations" || pathname.startsWith("/quotations/");
    case "/sales-orders":
      return pathname === "/sales-orders" || pathname.startsWith("/sales-orders/");
    case "/projects":
      return pathname === "/projects" || pathname.startsWith("/projects/");
    case "/leaves":
      return pathname === "/leaves" || pathname.startsWith("/leaves/");
    case "/invoices":
      return pathname === "/invoices" || pathname.startsWith("/invoices/");
    case "/payments":
      return pathname === "/payments";
    case "/expenses":
      return pathname === "/expenses" || pathname.startsWith("/expenses/");
    case "/vendor-bills":
      return pathname === "/vendor-bills" || pathname.startsWith("/vendor-bills/");
    case "/purchase-orders":
      return pathname === "/purchase-orders" || pathname.startsWith("/purchase-orders/");
    case "/inventory":
      return pathname === "/inventory" || pathname.startsWith("/inventory/");
    case "/stock-movements":
      return pathname === "/stock-movements" || pathname.startsWith("/stock-movements/");
    case "/warehouses":
      return pathname === "/warehouses" || pathname.startsWith("/warehouses/");
    case "/client-notes":
      return (pathname === "/client-notes" || pathname.startsWith("/client-notes/")) && pathname !== "/client-notes/follow-ups";
    case "/sales-reports":
      return pathname === "/sales-reports";
    case "/tax-reports":
      return pathname === "/tax-reports";
    case "/pl-reports":
      return pathname === "/pl-reports";
    case "/customer-ledger":
      return pathname === "/customer-ledger" || pathname.startsWith("/customer-ledger/");
    case "/vendor-ledger":
      return pathname === "/vendor-ledger" || pathname.startsWith("/vendor-ledger/");
    case "/documents":
      return pathname === "/documents" || pathname.startsWith("/documents/");
    case "/contacts":
      return pathname === "/contacts" || pathname.startsWith("/contacts/");
    case "/products":
      return pathname === "/products" || pathname.startsWith("/products/");
    case "/admin/company":
      return pathname === "/admin/company";
    case "/admin/users":
      return pathname === "/admin/users";
    case "/admin/numbering-config":
      return pathname === "/admin/numbering-config";
    case "/admin/activity-logs":
      return pathname === "/admin/activity-logs";
    case "/admin/system-config":
      return pathname === "/admin/system-config";
    case "/admin/email-templates":
      return pathname === "/admin/email-templates";
    default:
      return pathname === to || pathname.startsWith(`${to}/`);
  }
}

function navLinkClass(pathname, to) {
  return `crm-nav-link${isNavActive(pathname, to) ? " crm-nav-link-active" : ""}`;
}

function DashboardLayout({ title, roleLabel, children }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const navRef = useRef(null);

  useEffect(() => {
    if (localStorage.getItem("token") && getPermissions().length === 0) {
      apiFetch("/users/me/permissions")
        .then((data) => setPermissions(data.permissions))
        .catch(() => {});
    }
  }, []);

  // Convert vertical mouse-wheel events to horizontal scroll on the nav strip
  useEffect(() => {
    const el = navRef.current;
    if (!el) return;
    const onWheel = (e) => {
      if (e.deltaY === 0) return;
      e.preventDefault();
      el.scrollLeft += e.deltaY;
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
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
    <div className="crm-dashboard">
      <header className="crm-dashboard-header">
        <div className="crm-dashboard-title">
          <p className="crm-role-badge">{roleLabel}</p>
          <h1>{title}</h1>
        </div>
        <div className="crm-dashboard-nav-wrap">
          <nav className="crm-dashboard-nav" ref={navRef}>
            <Link to="/profile" className={navLinkClass(pathname, "/profile")}>
              My Profile
            </Link>
            {hasPermission("leads.view") && (
              <Link to="/leads" className={navLinkClass(pathname, "/leads")}>
                Leads
              </Link>
            )}
            {hasPermission("deals.view") && (
              <Link to="/pipeline" className={navLinkClass(pathname, "/pipeline")}>
                Pipeline
              </Link>
            )}
            {hasPermission("reminders.view") && (
              <Link to="/follow-ups" className={navLinkClass(pathname, "/follow-ups")}>
                Follow-ups
              </Link>
            )}
            {hasPermission("leaves.view") && (
              <Link to="/leaves" className={navLinkClass(pathname, "/leaves")}>
                Leave
              </Link>
            )}
            {hasPermission("quotations.view") && (
              <Link to="/quotations" className={navLinkClass(pathname, "/quotations")}>
                Quotations
              </Link>
            )}
            {hasPermission("sales_orders.view") && (
              <Link to="/sales-orders" className={navLinkClass(pathname, "/sales-orders")}>
                Orders
              </Link>
            )}
            {hasPermission("projects.view") && (
              <Link to="/projects" className={navLinkClass(pathname, "/projects")}>
                Projects
              </Link>
            )}
            {hasPermission("invoices.view") && (
              <Link to="/invoices" className={navLinkClass(pathname, "/invoices")}>
                Invoices
              </Link>
            )}
            {hasPermission("payments.view") && (
              <Link to="/payments" className={navLinkClass(pathname, "/payments")}>
                Payments
              </Link>
            )}
            {hasPermission("expenses.view") && (
              <Link to="/expenses" className={navLinkClass(pathname, "/expenses")}>
                Expenses
              </Link>
            )}
            {hasPermission("purchase_orders.view") && (
              <Link to="/purchase-orders" className={navLinkClass(pathname, "/purchase-orders")}>
                Purchase Orders
              </Link>
            )}
            {hasPermission("vendor_bills.view") && (
              <Link to="/vendor-bills" className={navLinkClass(pathname, "/vendor-bills")}>
                Vendor Bills
              </Link>
            )}
            {(hasPermission("vendor_ledger.view") || hasPermission("vendor_bills.view")) && (
              <Link to="/vendor-ledger" className={navLinkClass(pathname, "/vendor-ledger")}>
                Vendor Ledger
              </Link>
            )}
            {hasPermission("inventory.view") && (
              <Link to="/inventory" className={navLinkClass(pathname, "/inventory")}>
                Inventory
              </Link>
            )}
            {hasPermission("stock_movements.view") && (
              <Link to="/stock-movements" className={navLinkClass(pathname, "/stock-movements")}>
                Stock In / Out
              </Link>
            )}
            {hasPermission("warehouses.view") && (
              <Link to="/warehouses" className={navLinkClass(pathname, "/warehouses")}>
                Warehouses
              </Link>
            )}
            {hasPermission("client_notes.view") && (
              <Link to="/client-notes" className={navLinkClass(pathname, "/client-notes")}>
                Notes
              </Link>
            )}
            {(hasPermission("files.view") || hasPermission("files.view_own")) && (
              <Link to="/documents" className={navLinkClass(pathname, "/documents")}>
                Documents
              </Link>
            )}
            {hasPermission("reports.view") && (
              <Link to="/sales-reports" className={navLinkClass(pathname, "/sales-reports")}>
                Sales Reports
              </Link>
            )}
            {(hasPermission("customer_ledger.view") || hasPermission("invoices.view") || hasPermission("payments.view")) && (
              <Link to="/customer-ledger" className={navLinkClass(pathname, "/customer-ledger")}>
                Customer Ledger
              </Link>
            )}
            {(hasPermission("tax_reports.view") || hasPermission("reports.view_financial")) && (
              <Link to="/tax-reports" className={navLinkClass(pathname, "/tax-reports")}>
                GST / Tax Reports
              </Link>
            )}
            {(hasPermission("pl_reports.view") || hasPermission("reports.view_financial")) && (
              <Link to="/pl-reports" className={navLinkClass(pathname, "/pl-reports")}>
                P&L Reports
              </Link>
            )}
            {hasPermission("contacts.view") && (
              <Link to="/contacts" className={navLinkClass(pathname, "/contacts")}>
                Contacts
              </Link>
            )}
            {hasPermission("products.view") && (
              <Link to="/products" className={navLinkClass(pathname, "/products")}>
                Products
              </Link>
            )}
            {hasPermission("company.view") && (
              <Link to="/admin/company" className={navLinkClass(pathname, "/admin/company")}>
                Company
              </Link>
            )}
            {hasPermission("users.view") && (
              <Link to="/admin/users" className={navLinkClass(pathname, "/admin/users")}>
                Users
              </Link>
            )}
            {hasPermission("numbering_config.view") && (
              <Link to="/admin/numbering-config" className={navLinkClass(pathname, "/admin/numbering-config")}>
                Numbering Config
              </Link>
            )}
            {hasPermission("activity.view") && (
              <Link to="/admin/activity-logs" className={navLinkClass(pathname, "/admin/activity-logs")}>
                Activity Logs
              </Link>
            )}
            <Link to="/admin/system-config" className={navLinkClass(pathname, "/admin/system-config")}>
              System Config
            </Link>
            <Link to="/admin/email-templates" className={navLinkClass(pathname, "/admin/email-templates")}>
              Email Templates
            </Link>
          </nav>
          <NotificationBell />
          <button
            type="button"
            className="crm-btn crm-btn-outline crm-btn-sm crm-nav-logout"
            onClick={handleLogout}
          >
            Logout
          </button>
        </div>
      </header>
      <main className="crm-dashboard-main">{children}</main>
    </div>
  );
}

export default DashboardLayout;
