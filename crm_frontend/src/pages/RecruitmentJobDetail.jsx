import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import RecruitmentAddApplicant from "../components/RecruitmentAddApplicant";
import { apiFetch } from "../utils/api";
import { hasPermission } from "../utils/permissions";
import { APPLICANT_STATUS_LABELS, JOB_STATUS_LABELS, applicantBadgeClass, jobBadgeClass } from "../utils/recruitment";

const PIPELINE_STATUSES = ["screening", "interview", "offered", "hired", "rejected"];

function RecruitmentJobDetail() {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const role = localStorage.getItem("role") || "Staff";
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const canManage = hasPermission("recruitment.manage");
  const [showAddApplicant, setShowAddApplicant] = useState(searchParams.get("add") === "1");

  const load = () => apiFetch(`/recruitment/jobs/${id}`).then(setJob).catch((err) => setError(err.message));

  useEffect(() => {
    load();
  }, [id]);

  useEffect(() => {
    if (searchParams.get("add") === "1") {
      setShowAddApplicant(true);
    }
  }, [searchParams]);

  const closeAddPanel = () => {
    setShowAddApplicant(false);
    if (searchParams.get("add")) {
      searchParams.delete("add");
      setSearchParams(searchParams, { replace: true });
    }
  };

  const updateStatus = async (applicantId, status) => {
    try {
      await apiFetch(`/recruitment/applicants/${applicantId}`, {
        method: "PUT",
        body: JSON.stringify({ status }),
      });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (!job && !error) {
    return <DashboardLayout title="Job" roleLabel={role}><div className="crm-panel"><p>Loading…</p></div></DashboardLayout>;
  }

  return (
    <DashboardLayout title={job?.title || "Job"} roleLabel={role}>
      <div className="crm-panel crm-recruitment-page">
        <Link to="/recruitment" className="crm-link crm-link-left">← Recruitment</Link>
        {error && <p className="crm-error crm-mt">{error}</p>}
        {job && (
          <>
            <div className="crm-detail-header crm-mt">
              <div>
                <h2 className="crm-recruitment-job-title">{job.job_code} — {job.title}</h2>
                <p className="crm-text-secondary">{job.department}</p>
              </div>
              <div className="crm-inline-actions">
                {canManage && (
                  <button
                    type="button"
                    className="crm-btn crm-btn-sm crm-btn-inline"
                    onClick={() => setShowAddApplicant((open) => !open)}
                  >
                    {showAddApplicant ? "Hide form" : "+ Add applicant"}
                  </button>
                )}
                <span className={jobBadgeClass(job.status)}>{JOB_STATUS_LABELS[job.status]}</span>
              </div>
            </div>

            {job.description && <p className="crm-recruitment-job-description">{job.description}</p>}

            {canManage && showAddApplicant && (
              <RecruitmentAddApplicant
                jobId={Number(id)}
                jobs={[job]}
                onSuccess={() => {
                  closeAddPanel();
                  load();
                }}
                onCancel={closeAddPanel}
              />
            )}

            <section className="crm-entity-section">
              <h3 className="crm-section-title">Applicants ({job.applicants?.length || 0})</h3>

              {(job.applicants || []).length === 0 && (
                <p className="crm-muted crm-mt">No applicants yet. Use “Add applicant” above to register the first candidate.</p>
              )}

              <div className="crm-recruitment-applicant-list">
                {(job.applicants || []).map((a) => (
                  <article key={a.id} className="crm-recruitment-applicant-card">
                    <div className="crm-detail-header">
                      <div>
                        <strong className="crm-applicant-name">{a.name}</strong>
                        <p className="crm-text-secondary">{a.email}{a.phone ? ` · ${a.phone}` : ""}</p>
                      </div>
                      <span className={applicantBadgeClass(a.status)}>{APPLICANT_STATUS_LABELS[a.status]}</span>
                    </div>
                    {a.resume_summary && <p className="crm-recruitment-applicant-summary">{a.resume_summary}</p>}
                    {canManage && (
                      <div className="crm-applicant-stage-actions" role="group" aria-label="Update applicant stage">
                        {PIPELINE_STATUSES.map((s) => (
                          <button
                            key={s}
                            type="button"
                            className={`crm-btn crm-btn-sm crm-btn-outline${a.status === s ? " is-active" : ""}`}
                            onClick={() => updateStatus(a.id, s)}
                            disabled={a.status === s}
                          >
                            {APPLICANT_STATUS_LABELS[s]}
                          </button>
                        ))}
                      </div>
                    )}
                  </article>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

export default RecruitmentJobDetail;
