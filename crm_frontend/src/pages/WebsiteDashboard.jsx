import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { ActionStatusMessages, ModuleNav, ModulePageHeader, ModuleSection } from "../components/ModulePage";
import { apiFetch } from "../utils/api";
import { hasPermission } from "../utils/permissions";

function WebsiteDashboard() {
  const role = localStorage.getItem("role") || "Staff";
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch("/website/dashboard")
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  return (
    <DashboardLayout title="Website" roleLabel={role}>
      <div className="crm-panel">
        <ModulePageHeader subtitle="Public site and lead capture">
          {data?.public_url && (
            <a href={data.public_url} target="_blank" rel="noreferrer" className="crm-btn crm-btn-sm crm-btn-outline">View public site</a>
          )}
          {hasPermission("website.manage") && (
            <Link to="/website/pages/new" className="crm-btn crm-btn-sm">New page</Link>
          )}
        </ModulePageHeader>

        <ActionStatusMessages error={error} />

        {data && (
          <>
            <div className="crm-stats-grid crm-mt">
              <div className="crm-stat-card"><span className="crm-stat-value">{data.published_pages}</span><span className="crm-stat-label">Published pages</span></div>
              <div className="crm-stat-card"><span className="crm-stat-value">{data.draft_pages}</span><span className="crm-stat-label">Draft pages</span></div>
              <div className="crm-stat-card"><span className="crm-stat-value">{data.blog_posts}</span><span className="crm-stat-label">Blog posts</span></div>
              <div className="crm-stat-card"><span className="crm-stat-value">{data.form_submissions_7d}</span><span className="crm-stat-label">Submissions (7d)</span></div>
            </div>

            <ModuleNav>
              <Link to="/website/pages" className="crm-btn crm-btn-sm crm-btn-outline">Pages</Link>
              <Link to="/website/forms" className="crm-btn crm-btn-sm crm-btn-outline">Forms</Link>
              <Link to="/website/blog" className="crm-btn crm-btn-sm crm-btn-outline">Blog</Link>
              {hasPermission("website.manage") && (
                <Link to="/website/settings" className="crm-btn crm-btn-sm crm-btn-outline">Settings</Link>
              )}
            </ModuleNav>

            <ModuleSection title="Recent form submissions">
              {data.recent_submissions.length === 0 ? (
                <p className="crm-muted">No submissions yet. Publish a page with a form to capture leads.</p>
              ) : (
                <table className="crm-table crm-mt">
                  <thead>
                    <tr><th>Preview</th><th>Form</th><th>Lead</th><th>When</th></tr>
                  </thead>
                  <tbody>
                    {data.recent_submissions.map((s) => (
                      <tr key={s.id}>
                        <td>{s.preview}</td>
                        <td>{s.form_name}</td>
                        <td>{s.lead_id ? <Link to={`/leads/${s.lead_id}`}>#{s.lead_id}</Link> : "—"}</td>
                        <td>{new Date(s.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </ModuleSection>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

export default WebsiteDashboard;
