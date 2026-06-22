import { useCallback, useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom";
import { apiFetch } from "../utils/api";

const POLL_INTERVAL_MS = 30_000; // 30 seconds

/** Format an ISO timestamp into a human-friendly relative string. */
function timeAgo(isoString) {
  if (!isoString) return "";
  const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

/** Map notification type → accent colour (matches crm.css tokens). */
const TYPE_COLOR = {
  INFO: "var(--crm-accent)",
  SUCCESS: "var(--crm-employee)",
  WARNING: "var(--crm-user)",
  ERROR: "var(--crm-danger)",
};

function NotificationBell() {
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  // Position of the dropdown, calculated from the bell button's bounding rect
  const [dropdownPos, setDropdownPos] = useState({ top: 0, right: 0 });

  const bellRef = useRef(null);
  const dropdownRef = useRef(null);

  // ─── fetch unread count (lightweight, runs on poll) ───────────────────────
  const fetchUnreadCount = useCallback(async () => {
    try {
      const data = await apiFetch("/notifications/unread-count");
      setUnreadCount(data.count ?? 0);
    } catch {
      // silently ignore — user may not be logged in yet
    }
  }, []);

  // ─── fetch full notification list (only when dropdown opens) ─────────────
  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch("/notifications?page=1&limit=30");
      setNotifications(data.items ?? []);
    } catch {
      setNotifications([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // ─── initial fetch + polling ──────────────────────────────────────────────
  useEffect(() => {
    fetchUnreadCount();
    const timer = setInterval(fetchUnreadCount, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [fetchUnreadCount]);

  // ─── fetch + position dropdown when it opens ─────────────────────────────
  useEffect(() => {
    if (!open) return;
    fetchNotifications();
    // Calculate position relative to viewport so the portal renders correctly
    if (bellRef.current) {
      const rect = bellRef.current.getBoundingClientRect();
      setDropdownPos({
        top: rect.bottom + window.scrollY + 8,
        right: window.innerWidth - rect.right - window.scrollX,
      });
    }
  }, [open, fetchNotifications]);

  // ─── close dropdown when clicking outside ────────────────────────────────
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      const clickedBell = bellRef.current && bellRef.current.contains(e.target);
      const clickedDropdown = dropdownRef.current && dropdownRef.current.contains(e.target);
      if (!clickedBell && !clickedDropdown) {
        setOpen(false);
      }
    };
    // Use capture phase so it fires before any stopPropagation inside the dropdown
    document.addEventListener("mousedown", handler, true);
    return () => document.removeEventListener("mousedown", handler, true);
  }, [open]);

  // ─── mark single notification as read ────────────────────────────────────
  const markRead = async (id) => {
    try {
      await apiFetch(`/notifications/${id}/read`, { method: "PATCH" });
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      // ignore
    }
  };

  // ─── mark all as read ─────────────────────────────────────────────────────
  const markAllRead = async () => {
    try {
      await apiFetch("/notifications/read-all", { method: "PATCH" });
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // ignore
    }
  };

  const hasUnread = unreadCount > 0;

  // Dropdown rendered via a portal so it escapes overflow:hidden ancestors
  const dropdown = open
    ? ReactDOM.createPortal(
        <div
          ref={dropdownRef}
          className="notif-dropdown"
          role="region"
          aria-label="Notifications panel"
          style={{
            position: "absolute",
            top: dropdownPos.top,
            right: dropdownPos.right,
          }}
        >
          {/* Header */}
          <div className="notif-dropdown-header">
            <span className="notif-dropdown-title">Notifications</span>
            {hasUnread && (
              <button
                type="button"
                className="notif-mark-all-btn"
                onClick={markAllRead}
              >
                Mark all read
              </button>
            )}
          </div>

          {/* Body */}
          <div className="notif-dropdown-body">
            {loading && <p className="notif-empty">Loading…</p>}

            {!loading && notifications.length === 0 && (
              <p className="notif-empty">No notifications yet.</p>
            )}

            {!loading &&
              notifications.map((n) => (
                <div
                  key={n.id}
                  className={`notif-item${n.is_read ? "" : " notif-item--unread"}`}
                >
                  <span
                    className="notif-type-dot"
                    style={{
                      background: TYPE_COLOR[n.type] ?? TYPE_COLOR.INFO,
                    }}
                    aria-hidden="true"
                  />
                  <div className="notif-item-body">
                    <p className="notif-item-title">{n.title}</p>
                    <p className="notif-item-message">{n.message}</p>
                    <div className="notif-item-meta">
                      <span className="notif-item-time">
                        {timeAgo(n.created_at)}
                      </span>
                      {!n.is_read && (
                        <button
                          type="button"
                          className="notif-read-btn"
                          onClick={() => markRead(n.id)}
                        >
                          Mark read
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
          </div>
        </div>,
        document.body
      )
    : null;

  return (
    <>
      {/* Bell button — lives in the header */}
      <button
        ref={bellRef}
        type="button"
        className="notif-bell-btn"
        onClick={() => setOpen((v) => !v)}
        aria-label={`Notifications${hasUnread ? `, ${unreadCount} unread` : ""}`}
        aria-haspopup="true"
        aria-expanded={open}
      >
        <span className="notif-bell-icon" aria-hidden="true">🔔</span>
        {hasUnread && (
          <span className="notif-badge" aria-hidden="true">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown portal — renders directly into document.body, escaping all clipping ancestors */}
      {dropdown}
    </>
  );
}

export default NotificationBell;
