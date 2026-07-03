import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Star, ChevronDown, ChevronUp } from "lucide-react";

import {
  APP_CATEGORIES,
  CRM_APPS,
  filterAppsByPermission,
  groupAppsByCategory,
} from "../config/appCatalog";
import { hasPermission } from "../utils/permissions";
import AppIcon from "./AppIcon";

function AppTile({ app, asLink = true, isFavorite = false, onToggleFavorite = null }) {
  const inner = (
    <>
      <div className="crm-app-tile-glow" />
      <div className="crm-app-tile-icon-box" style={{ borderColor: `${app.color}22` }}>
        <AppIcon name={app.icon} color={app.color} size={28} />
      </div>
      <div className="crm-app-tile-content-box">
        <div className="crm-app-tile-label-row">
          <span className="crm-app-tile-label">{app.label}</span>
          {onToggleFavorite && (
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onToggleFavorite(app.id);
              }}
              className={`crm-app-tile-favorite${isFavorite ? " active" : ""}`}
              title={isFavorite ? "Remove from favorites" : "Add to favorites"}
            >
              <Star size={14} fill={isFavorite ? "#F59E0B" : "transparent"} />
            </button>
          )}
        </div>
        {app.subtitle && (
          <span className="crm-app-tile-sub">{app.subtitle}</span>
        )}
      </div>
      {app.comingSoon && (
        <span className="crm-app-tile-badge" style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", fontSize: "0.65rem", padding: "1px 5px", borderRadius: "6px" }}>Soon</span>
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

  const [favorites, setFavorites] = useState([]);
  const [collapsedCategories, setCollapsedCategories] = useState({});

  // Sync favorites from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem("crmFavorites");
      if (saved) setFavorites(JSON.parse(saved));
      else setFavorites(["leads", "invoices", "projects"]);
    } catch {
      setFavorites(["leads", "invoices", "projects"]);
    }
  }, []);

  const handleToggleFavorite = (appId) => {
    setFavorites((prev) => {
      const next = prev.includes(appId)
        ? prev.filter((id) => id !== appId)
        : [...prev, appId];
      localStorage.setItem("crmFavorites", JSON.stringify(next));
      // Dispatch a storage event so that DashboardLayout sidebar listens and re-renders immediately!
      window.dispatchEvent(new Event("storage"));
      return next;
    });
  };

  const toggleCategoryCollapse = (categoryKey) => {
    setCollapsedCategories((prev) => ({
      ...prev,
      [categoryKey]: !prev[categoryKey],
    }));
  };

  if (visible.length === 0) return null;

  const groups = groupByCategory ? groupAppsByCategory(visible) : { all: visible };
  const groupKeys = groupByCategory
    ? Object.keys(APP_CATEGORIES).filter((k) => groups[k]?.length)
    : ["all"];

  return (
    <section className={`crm-app-launcher ${className}`.trim()}>
      {(title || subtitle) && (
        <header className="crm-app-launcher-header">
          {title && <h2 style={{ fontSize: "1.1rem", fontWeight: "700" }}>{title}</h2>}
          {subtitle && <p className="crm-muted">{subtitle}</p>}
        </header>
      )}

      {groupKeys.map((key) => {
        const items = groups[key];
        if (!items?.length) return null;
        const isCollapsed = collapsedCategories[key];

        return (
          <div key={key} className="crm-app-launcher-group">
            {groupByCategory && key !== "all" && (
              <header className="crm-premium-launcher-category-header">
                <h3 className="crm-premium-launcher-category-title">
                  {APP_CATEGORIES[key]}
                </h3>
                <button
                  type="button"
                  onClick={() => toggleCategoryCollapse(key)}
                  className="crm-premium-launcher-collapse-btn"
                >
                  {isCollapsed ? (
                    <>
                      <span>Expand</span>
                      <ChevronDown size={14} />
                    </>
                  ) : (
                    <>
                      <span>Collapse</span>
                      <ChevronUp size={14} />
                    </>
                  )}
                </button>
              </header>
            )}
            
            {!isCollapsed && (
              <div className="crm-app-grid">
                {items.map((app) => (
                  <AppTile
                    key={app.id}
                    app={app}
                    asLink={asLink}
                    isFavorite={favorites.includes(app.id)}
                    onToggleFavorite={handleToggleFavorite}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}

export default AppLauncher;
