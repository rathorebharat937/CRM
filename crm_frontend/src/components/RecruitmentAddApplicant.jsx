import { useState } from "react";

import { apiFetch } from "../utils/api";

const EMPTY_FORM = { name: "", email: "", phone: "", experience_years: "", resume_summary: "" };

function RecruitmentAddApplicant({ jobs, jobId, onSuccess, onCancel }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [selectedJobId, setSelectedJobId] = useState(jobId ? String(jobId) : "");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const targetJobId = jobId || selectedJobId;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!targetJobId) {
      setError("Select a job opening first.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      await apiFetch(`/recruitment/jobs/${targetJobId}/applicants`, {
        method: "POST",
        body: JSON.stringify({
          ...form,
          experience_years: form.experience_years ? parseFloat(form.experience_years) : null,
        }),
      });
      setForm(EMPTY_FORM);
      if (!jobId) setSelectedJobId("");
      onSuccess?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="crm-recruitment-add-panel" onSubmit={handleSubmit}>
      <div className="crm-detail-header">
        <h3>Add applicant</h3>
        {onCancel && (
          <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>

      {!jobId && (
        <div className="crm-form-field">
          <label htmlFor="recruitment-job-select">Job opening *</label>
          <select
            id="recruitment-job-select"
            required
            value={selectedJobId}
            onChange={(e) => setSelectedJobId(e.target.value)}
          >
            <option value="">Select job…</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.job_code} — {job.title} ({job.department})
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="crm-form-grid">
        <div>
          <label htmlFor="recruitment-applicant-name">Name *</label>
          <input
            id="recruitment-applicant-name"
            required
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          />
        </div>
        <div>
          <label htmlFor="recruitment-applicant-email">Email *</label>
          <input
            id="recruitment-applicant-email"
            type="email"
            required
            value={form.email}
            onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
          />
        </div>
        <div>
          <label htmlFor="recruitment-applicant-phone">Phone</label>
          <input
            id="recruitment-applicant-phone"
            value={form.phone}
            onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
          />
        </div>
        <div>
          <label htmlFor="recruitment-applicant-exp">Experience (years)</label>
          <input
            id="recruitment-applicant-exp"
            type="number"
            step="0.5"
            value={form.experience_years}
            onChange={(e) => setForm((f) => ({ ...f, experience_years: e.target.value }))}
          />
        </div>
        <div className="crm-span-2">
          <label htmlFor="recruitment-applicant-summary">Summary</label>
          <textarea
            id="recruitment-applicant-summary"
            className="crm-textarea"
            rows={2}
            value={form.resume_summary}
            onChange={(e) => setForm((f) => ({ ...f, resume_summary: e.target.value }))}
          />
        </div>
      </div>

      {error && <p className="crm-error">{error}</p>}

      <div className="crm-recruitment-add-actions">
        <button type="submit" className="crm-btn crm-btn-sm crm-btn-inline" disabled={saving}>
          {saving ? "Saving…" : "Add applicant"}
        </button>
      </div>
    </form>
  );
}

export default RecruitmentAddApplicant;
