import { Link } from "react-router-dom";

import {
  APP_CATEGORIES,
  CRM_APPS,
  filterAppsByPermission,
  groupAppsByCategory,
} from "../config/appCatalog";
import { hasPermission } from "../utils/permissions";
import AppIcon from "./AppIcon";

function AppTile({ app, asLink = true }) {
  const inner = (
    <>
      <AppIcon name={app.icon} color={app.color} />
      <span className="crm-app-tile-label">{app.label}</span>
      {app.subtitle && (
        <span className="crm-app-tile-sub">{app.subtitle}</span>
      )}
      {app.comingSoon && (
        <span className="crm-app-tile-badge">Soon</span>
      )}
    </>
  );

  if (!asLink || !app.path) {
    return (
      <div className="crm-app-tile crm-app-tile-static" style={{ "--app-accent": app.color }}>
        {inner}
      </div>
    );
  }

  return (
    <Link
      to={app.path}
      className={`crm-app-tile${app.comingSoon ? " crm-app-tile-coming-soon" : ""}`}
      style={{ "--app-accent": app.color }}
      aria-label={app.label}
    >
      {inner}
    </Link>
  );
}

function AppLauncher({
  apps = CRM_APPS,
  title = "Your apps",
  subtitle,
  groupByCategory = true,
  filterByPermission = true,
  asLink = true,
  className = "",
}) {
  const visible = filterByPermission
    ? filterAppsByPermission(apps, hasPermission)
    : apps;

  if (visible.length === 0) return null;

  const groups = groupByCategory ? groupAppsByCategory(visible) : { all: visible };
  const groupKeys = groupByCategory
    ? Object.keys(APP_CATEGORIES).filter((k) => groups[k]?.length)
    : ["all"];

  return (
    <section className={`crm-app-launcher ${className}`.trim()}>
      {(title || subtitle) && (
        <header className="crm-app-launcher-header">
          {title && <h2>{title}</h2>}
          {subtitle && <p className="crm-muted">{subtitle}</p>}
        </header>
      )}

      {groupKeys.map((key) => {
        const items = groups[key];
        if (!items?.length) return null;

        return (
          <div key={key} className="crm-app-launcher-group">
            {groupByCategory && key !== "all" && (
              <h3 className="crm-app-launcher-category">{APP_CATEGORIES[key]}</h3>
            )}
            <div className="crm-app-grid">
              {items.map((app) => (
                <AppTile key={app.id} app={app} asLink={asLink} />
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
}

export default AppLauncher;
