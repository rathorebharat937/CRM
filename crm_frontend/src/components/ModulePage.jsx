import { Link } from "react-router-dom";

/** Standard hub header: subtitle left, action buttons right. */
export function ModulePageHeader({ subtitle, children }) {
  return (
    <div className="crm-detail-header">
      <p className="crm-muted">{subtitle}</p>
      {children ? <div className="crm-inline-actions">{children}</div> : null}
    </div>
  );
}

/** Secondary nav row (Pages, Orders, Work orders, etc.). */
export function ModuleNav({ children }) {
  if (!children) return null;
  return <div className="crm-module-nav crm-mt">{children}</div>;
}

/** Section with consistent heading spacing inside module panels. */
export function ModuleSection({ title, children, className = "" }) {
  return (
    <section className={`crm-module-section crm-mt ${className}`.trim()}>
      {title ? <h3>{title}</h3> : null}
      {children}
    </section>
  );
}

export function ModuleBackLink({ to, children }) {
  return (
    <Link to={to} className="crm-muted">
      {children}
    </Link>
  );
}

/** Shown when a module's is_enabled flag is false. */
export function ModuleDisabledBanner({ moduleName }) {
  return (
    <p className="crm-alert crm-alert-warn crm-mt">
      {moduleName} is disabled. Enable it in Settings to use this module.
    </p>
  );
}

/** Hub action feedback — error OR success, never both. */
export function ActionStatusMessages({ error, success, successText }) {
  if (error) {
    return <p className="crm-error crm-mt">{error}</p>;
  }
  if (success) {
    return <p className="crm-success crm-mt">{successText}</p>;
  }
  return null;
}
