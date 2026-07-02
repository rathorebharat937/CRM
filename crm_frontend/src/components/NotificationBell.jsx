import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiFetch } from "../utils/api";
import { hasPermission } from "../utils/permissions";

function formatWhen(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

function NotificationBell() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [items, setItems] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [error, setError] = useState("");
  const wrapRef = useRef(null);

  const load = useCallback(() => {
    if (!hasPermission("notifications.view")) return;
    apiFetch("/notifications/unread-count")
      .then((d) => setUnread(d.unread_count || 0))
      .catch(() => setUnread(0));
  }, []);

  const loadList = useCallback(() => {
    if (!hasPermission("notifications.view")) return;
    setError("");
    apiFetch("/notifications?limit=50&unread_only=true")
      .then((d) => {
        setItems(d.items || []);
        setUnread(d.unread_count || 0);
      })
      .catch((err) => setError(err.message || "Could not load notifications"));
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 60000);
    return () => clearInterval(timer);
  }, [load]);

  useEffect(() => {
    if (open) {
      loadList();
    } else {
      setExpandedId(null);
    }
  }, [open, loadList]);

  useEffect(() => {
    const onDoc = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  if (!hasPermission("notifications.view")) return null;

  const dismiss = async (id) => {
    setItems((prev) => prev.filter((n) => n.id !== id));
    setUnread((c) => Math.max(0, c - 1));
    if (expandedId === id) setExpandedId(null);
    try {
      await apiFetch(`/notifications/${id}/read`, { method: "PATCH" });
      load();
    } catch {
      loadList();
    }
  };

  const openNotification = async (n) => {
    await dismiss(n.id);
    setOpen(false);
    if (n.link_path) {
      navigate(n.link_path);
    }
  };

  const toggleExpand = (n) => {
    setExpandedId((current) => (current === n.id ? null : n.id));
  };

  const clearAll = async () => {
    setItems([]);
    setUnread(0);
    setExpandedId(null);
    try {
      await apiFetch("/notifications/read-all", { method: "POST" });
    } catch {
      loadList();
    }
  };

  return (
    <div className="crm-notif-wrap" ref={wrapRef}>
      <button
        type="button"
        className="crm-notif-btn"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        aria-label="Open notifications"
        aria-expanded={open}
        title="Notifications — follow-ups, approvals, payments, tasks"
      >
        <span className="crm-notif-icon" aria-hidden>
          🔔
        </span>
        <span>Alerts</span>
        {unread > 0 && (
          <span className="crm-notif-badge" aria-label={`${unread} unread`}>
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div
          className="crm-notif-panel"
          role="dialog"
          aria-label="Notifications"
          onMouseDown={(e) => e.stopPropagation()}
        >
          <div className="crm-notif-panel-header">
            <strong>Notifications</strong>
            {items.length > 0 && (
              <button type="button" className="crm-link" onClick={clearAll}>
                Clear all
              </button>
            )}
          </div>
          <div className="crm-notif-list">
            {error && <p className="crm-error crm-pad-sm">{error}</p>}
            {!error && items.length === 0 && (
              <p className="crm-muted crm-pad-sm">No new notifications</p>
            )}
            {items.map((n) => {
              const isExpanded = expandedId === n.id;
              const preview =
                !isExpanded && n.message.length > 100
                  ? `${n.message.slice(0, 100).trim()}…`
                  : n.message;
              return (
                <div
                  key={n.id}
                  className={`crm-notif-item crm-notif-item-unread${isExpanded ? " crm-notif-item-expanded" : ""}`}
                >
                  <button
                    type="button"
                    className="crm-notif-item-toggle"
                    onClick={() => toggleExpand(n)}
                    aria-expanded={isExpanded}
                  >
                    <p className="crm-notif-title">{n.title}</p>
                    <p className="crm-muted crm-text-sm crm-notif-preview">{preview}</p>
                    {!isExpanded && n.message.length > 100 && (
                      <span className="crm-notif-more">Tap to read full message</span>
                    )}
                    <p className="crm-muted crm-text-sm crm-notif-when">{formatWhen(n.created_at)}</p>
                  </button>
                  {isExpanded && (
                    <div className="crm-inline-actions crm-mt-sm">
                      {n.link_path && (
                        <button
                          type="button"
                          className="crm-btn crm-btn-sm crm-btn-primary"
                          onClick={() => openNotification(n)}
                        >
                          Open
                        </button>
                      )}
                      <button
                        type="button"
                        className="crm-btn crm-btn-sm crm-btn-outline"
                        onClick={() => dismiss(n.id)}
                      >
                        {n.link_path ? "Dismiss" : "Done"}
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default NotificationBell;
