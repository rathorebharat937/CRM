import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";
import { hasPermission } from "../utils/permissions";
import {
  PRIORITY_LABELS,
  STATUS_LABELS,
  formatDate,
  priorityBadgeClass,
  statusBadgeClass,
} from "../utils/projects";

function Projects() {
  const [searchParams] = useSearchParams();
  const contactFilter = searchParams.get("contact_id") || "";
  const role = localStorage.getItem("role") || "Staff";
  const [data, setData] = useState({ items: [], total: 0, page: 1, limit: 20, kpis: null });
  const [meta, setMeta] = useState({ statuses: [] });
  const [status, setStatus] = useState("active");
  const [search, setSearch] = useState("");
  const [mine, setMine] = useState(false);
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [sort, setSort] = useState("deadline");
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch("/projects/meta").then(setMeta).catch(() => {});
  }, []);

  const load = (page = 1) => {
    const params = new URLSearchParams({ page: String(page), limit: "20", sort });
    if (status) params.set("status", status);
    if (mine) params.set("mine", "true");
    if (overdueOnly) params.set("overdue_only", "true");
    if (contactFilter) params.set("contact_id", contactFilter);
    if (search.trim()) params.set("search", search.trim());
    apiFetch(`/projects?${params}`).then(setData).catch((err) => setError(err.message));
  };

  useEffect(() => { load(1); }, [status, mine, overdueOnly, sort, contactFilter]);

  const totalPages = Math.max(1, Math.ceil(data.total / data.limit));
  const kpis = data.kpis;

  return (
    <DashboardLayout title="Projects" roleLabel={role}>
      <div className="crm-panel">
        <div className="crm-detail-header">
          <p className="crm-muted">{data.total} project{data.total === 1 ? "" : "s"}</p>
          <div className="crm-inline-actions">
            <Link to="/projects/my-tasks" className="crm-btn crm-btn-sm crm-btn-outline">My tasks</Link>
            {hasPermission("projects.create") && (
              <Link to="/projects/new" className="crm-btn crm-btn-sm crm-btn-inline">+ New project</Link>
            )}
          </div>
        </div>

        {kpis && (
          <div className="crm-stats-grid crm-mt">
            <div className="crm-stat-card"><p className="crm-stat-label">Active projects</p><p className="crm-stat-value">{kpis.active_projects}</p></div>
            <div className="crm-stat-card"><p className="crm-stat-label">Overdue projects</p><p className="crm-stat-value">{kpis.overdue_projects}</p></div>
            <div className="crm-stat-card"><p className="crm-stat-label">My open tasks</p><p className="crm-stat-value">{kpis.my_open_tasks}</p></div>
            <div className="crm-stat-card"><p className="crm-stat-label">Completed this month</p><p className="crm-stat-value">{kpis.completed_this_month}</p></div>
          </div>
        )}

        <div className="crm-contacts-toolbar crm-mt">
          <form onSubmit={(e) => { e.preventDefault(); load(1); }} className="crm-search-form">
            <input placeholder="Search name, code, client…" value={search} onChange={(e) => setSearch(e.target.value)} />
            <button type="submit" className="crm-btn crm-btn-sm">Search</button>
          </form>
          <div className="crm-filters">
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              {(meta.statuses || []).map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="deadline">Deadline</option>
              <option value="progress">Progress</option>
              <option value="updated">Last updated</option>
              <option value="name">Name</option>
            </select>
            <label className="crm-consent-check">
              <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} />
              My projects
            </label>
            <label className="crm-consent-check">
              <input type="checkbox" checked={overdueOnly} onChange={(e) => setOverdueOnly(e.target.checked)} />
              Overdue
            </label>
          </div>
        </div>

        {error && <p className="crm-error crm-mt">{error}</p>}

        {data.items.length === 0 ? (
          <div className="crm-empty-state crm-mt">
            <p>No projects found.</p>
          </div>
        ) : (
          <div className="crm-table-wrap crm-mt">
            <table className="crm-table">
              <thead>
                <tr>
                  <th>Project</th>
                  <th>Client</th>
                  <th>Manager</th>
                  <th>Stage</th>
                  <th>Progress</th>
                  <th>Deadline</th>
                  <th>Status</th>
                  <th>Open</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.items.map((p) => (
                  <tr key={p.id} className={p.is_overdue || p.overdue_task_count > 0 ? "crm-row-overdue" : ""}>
                    <td>
                      <Link to={`/projects/${p.id}`} className="crm-nav-link">{p.name}</Link>
                      {p.project_number && <div className="crm-muted crm-text-sm">{p.project_number}</div>}
                    </td>
                    <td>{p.contact_name || "—"}</td>
                    <td>{p.project_manager_name || "—"}</td>
                    <td>{p.stage_summary || "—"}</td>
                    <td>
                      <div className="crm-proj-progress-inline">
                        <div className="crm-proj-progress-bar"><span style={{ width: `${p.progress_percent}%` }} /></div>
                        <span>{p.progress_percent}%</span>
                      </div>
                    </td>
                    <td>
                      {formatDate(p.deadline)}
                      {p.is_overdue && <span className="crm-badge crm-badge-danger crm-ml">Overdue</span>}
                    </td>
                    <td><span className={statusBadgeClass(p.status)}>{STATUS_LABELS[p.status] || p.status}</span></td>
                    <td>
                      {p.open_task_count}
                      {p.overdue_task_count > 0 && (
                        <span className="crm-badge crm-badge-danger crm-ml">{p.overdue_task_count} late</span>
                      )}
                    </td>
                    <td><Link to={`/projects/${p.id}`} className="crm-btn crm-btn-sm crm-btn-outline">View</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="crm-pagination crm-mt">
            <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" disabled={data.page <= 1} onClick={() => load(data.page - 1)}>Previous</button>
            <span className="crm-muted">Page {data.page} of {totalPages}</span>
            <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" disabled={data.page >= totalPages} onClick={() => load(data.page + 1)}>Next</button>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

export default Projects;
