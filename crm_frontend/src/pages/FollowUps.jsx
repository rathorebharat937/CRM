import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";
import { hasPermission } from "../utils/permissions";

function FollowUps() {
  const role = localStorage.getItem("role") || "Staff";
  const [filter, setFilter] = useState("all");
  const [stats, setStats] = useState(null);
  const [queue, setQueue] = useState({ items: [], total: 0 });
  const [error, setError] = useState("");

  const load = () => {
    Promise.all([
      apiFetch("/reminders/stats/summary"),
      apiFetch(`/reminders/queue/unified?filter=${filter}`),
    ])
      .then(([summary, data]) => {
        setStats(summary);
        setQueue(data);
        setError("");
      })
      .catch((err) => setError(err.message));
  };

  useEffect(() => {
    load();
  }, [filter]);

  const handleComplete = async (item) => {
    try {
      if (item.source === "reminder") {
        await apiFetch(`/reminders/${item.id}/complete`, { method: "PATCH" });
      } else {
        await apiFetch(`/client-notes/${item.id}/complete-followup`, { method: "POST" });
      }
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const canComplete = (item) => {
    if (item.source === "reminder") return hasPermission("reminders.edit");
    return hasPermission("client_notes.manage_followups");
  };

  return (
    <DashboardLayout title="Follow-ups" roleLabel={role}>
      <div className="crm-panel">
        {stats && (
          <div className="crm-stat-strip">
            <div className="crm-stat-card">
              <span className="crm-stat-label">Due today</span>
              <strong>{stats.due_today}</strong>
            </div>
            <div className="crm-stat-card">
              <span className="crm-stat-label">Overdue</span>
              <strong>{stats.overdue}</strong>
            </div>
            <div className="crm-stat-card">
              <span className="crm-stat-label">Upcoming</span>
              <strong>{stats.upcoming}</strong>
            </div>
            <div className="crm-stat-card">
              <span className="crm-stat-label">Client note follow-ups</span>
              <strong>{stats.note_follow_ups_pending}</strong>
            </div>
          </div>
        )}

        <div className="crm-contacts-toolbar crm-mt">
          <div className="crm-filters">
            {["all", "due_today", "overdue", "upcoming"].map((f) => (
              <button
                key={f}
                type="button"
                className={`crm-btn crm-btn-sm ${filter === f ? "crm-btn-inline" : "crm-btn-outline"}`}
                onClick={() => setFilter(f)}
              >
                {f === "due_today" ? "Due today" : f.charAt(0).toUpperCase() + f.slice(1).replace("_", " ")}
              </button>
            ))}
          </div>
          {hasPermission("client_notes.manage_followups") && (
            <Link to="/client-notes/follow-ups" className="crm-btn crm-btn-sm crm-btn-outline">
              Client note queue
            </Link>
          )}
        </div>

        {error && <p className="crm-error crm-mt">{error}</p>}

        <div className="crm-table-wrap crm-mt">
          <table className="crm-table">
            <thead>
              <tr>
                <th>Due</th>
                <th>Task</th>
                <th>Related to</th>
                <th>Type</th>
                <th>Assigned</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {queue.items.length === 0 && (
                <tr>
                  <td colSpan={6} className="crm-muted">
                    No follow-ups in this view. You are all caught up.
                  </td>
                </tr>
              )}
              {queue.items.map((item) => (
                <tr key={`${item.source}-${item.id}`}>
                  <td>
                    <span className="crm-cell-primary">
                      {item.due_at ? new Date(item.due_at).toLocaleString() : "—"}
                    </span>
                    {item.is_overdue && <span className="crm-badge crm-deal-lost">Overdue</span>}
                    {item.is_due_today && !item.is_overdue && (
                      <span className="crm-badge crm-deal-proposal">Today</span>
                    )}
                  </td>
                  <td>
                    <span className="crm-cell-primary">{item.title}</span>
                    <span className="crm-cell-secondary">
                      {item.source === "reminder" ? "Reminder" : "Client note"}
                    </span>
                  </td>
                  <td>
                    {item.entity_path ? (
                      <Link to={item.entity_path} className="crm-nav-link">{item.subtitle || "View"}</Link>
                    ) : (
                      <span className="crm-text-secondary">{item.subtitle || "—"}</span>
                    )}
                  </td>
                  <td><span className="crm-text-secondary">{item.reminder_type}</span></td>
                  <td>{item.assigned_to_name || "—"}</td>
                  <td>
                    {canComplete(item) && (
                      <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={() => handleComplete(item)}>
                        Done
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardLayout>
  );
}

export default FollowUps;
