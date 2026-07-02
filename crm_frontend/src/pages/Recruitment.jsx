import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import RecruitmentAddApplicant from "../components/RecruitmentAddApplicant";
import { apiFetch } from "../utils/api";
import { hasPermission } from "../utils/permissions";
import { JOB_STATUS_LABELS, formatCurrency, formatDate, jobBadgeClass } from "../utils/recruitment";

function Recruitment() {
  const role = localStorage.getItem("role") || "Staff";
  const canManage = hasPermission("recruitment.manage");
  const [data, setData] = useState({ items: [], total: 0 });
  const [error, setError] = useState("");
  const [showAddApplicant, setShowAddApplicant] = useState(false);

  const load = () => {
    apiFetch("/recruitment/jobs?limit=50")
      .then(setData)
      .catch((err) => setError(err.message));
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <DashboardLayout title="Recruitment" roleLabel={role}>
      <div className="crm-panel crm-recruitment-page">
        <div className="crm-detail-header">
          <p className="crm-meta-sub">{data.total} job opening{data.total === 1 ? "" : "s"}</p>
          {canManage && (
            <button
              type="button"
              className="crm-btn crm-btn-sm crm-btn-inline"
              onClick={() => setShowAddApplicant((open) => !open)}
            >
              {showAddApplicant ? "Hide form" : "+ Add applicant"}
            </button>
          )}
        </div>

        {error && <p className="crm-error crm-mt">{error}</p>}

        {canManage && showAddApplicant && (
          <RecruitmentAddApplicant
            jobs={data.items}
            onSuccess={() => {
              setShowAddApplicant(false);
              load();
            }}
            onCancel={() => setShowAddApplicant(false)}
          />
        )}

        <div className="crm-recruitment-job-list crm-mt">
          {data.items.map((job) => (
            <article key={job.id} className="crm-recruitment-job-card">
              <div className="crm-detail-header">
                <div>
                  <h3 className="crm-recruitment-job-title">{job.job_code} — {job.title}</h3>
                  <p className="crm-text-secondary">
                    {job.department} · {job.applicant_count} applicant{job.applicant_count === 1 ? "" : "s"}
                  </p>
                </div>
                <span className={jobBadgeClass(job.status)}>{JOB_STATUS_LABELS[job.status]}</span>
              </div>
              <p className="crm-recruitment-job-meta">
                Posted {formatDate(job.posted_at)} · {formatCurrency(job.salary_min)} – {formatCurrency(job.salary_max)}
              </p>
              <div className="crm-recruitment-job-actions">
                <Link to={`/recruitment/jobs/${job.id}`} className="crm-btn crm-btn-sm crm-btn-outline">
                  View pipeline
                </Link>
                {canManage && (
                  <Link
                    to={`/recruitment/jobs/${job.id}?add=1`}
                    className="crm-btn crm-btn-sm crm-btn-outline"
                  >
                    Add applicant
                  </Link>
                )}
              </div>
            </article>
          ))}
        </div>

        {data.items.length === 0 && !error && <p className="crm-muted crm-mt">No job openings.</p>}
      </div>
    </DashboardLayout>
  );
}

export default Recruitment;
