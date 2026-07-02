import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";
import { DOMAIN_LABELS, dedupeWatchItems, formatPeriod, severityClass } from "../utils/aiReports";

function AiInsightRunDetail() {
  const { id } = useParams();
  const role = localStorage.getItem("role") || "Staff";
  const [run, setRun] = useState(null);
  const [error, setError] = useState("");
  const [expandedSection, setExpandedSection] = useState(null);

  useEffect(() => {
    apiFetch(`/ai-reports/runs/${id}`).then(setRun).catch((err) => setError(err.message));
  }, [id]);

  const sections = (run?.sections || []).filter((s) => s.domain !== "executive");
  const executive = run?.sections?.find((s) => s.domain === "executive");
  const watchItems = dedupeWatchItems(run?.watch_items || []);

  return (
    <DashboardLayout title="Insight detail" roleLabel={role}>
      <div className="crm-panel">
        <Link to="/ai-reports" className="crm-muted">← AI Reports</Link>
        {error && <p className="crm-error crm-mt">{error}</p>}
        {run && (
          <>
            <div className="crm-detail-header crm-mt">
              <div>
                <h2>{run.run_number}</h2>
                <p className="crm-muted">{formatPeriod(run.period_start, run.period_end)} · {run.status}</p>
              </div>
            </div>

            {run.error_message && <p className="crm-error crm-mt">{run.error_message}</p>}

            <div className="ai-reports-headline crm-mt">
              <h3>{run.executive_headline || executive?.headline || "Executive summary"}</h3>
              <p>{run.executive_summary || executive?.narrative}</p>
            </div>

            {watchItems.length > 0 && (
              <aside className="ai-reports-sidebar crm-mt">
                <h3>Top watch items</h3>
                <ul className="ai-reports-watch-list">
                  {watchItems.map((w) => (
                    <li key={`${w.severity}-${w.text}-${w.link_path || ""}`}>
                      <span className={severityClass(w.severity)}>{w.severity}</span>
                      <span className="ai-reports-watch-text">
                        {w.link_path ? <Link to={w.link_path}>{w.text}</Link> : w.text}
                      </span>
                    </li>
                  ))}
                </ul>
              </aside>
            )}

            <div className="ai-reports-sections">
            {sections.map((section) => (
              <div key={section.id} className="ai-reports-section">
                <p className="ai-reports-section-label">{DOMAIN_LABELS[section.domain] || section.domain}</p>
                <h3>{section.headline}</h3>
                <p>{section.narrative}</p>
                {section.bullets?.length > 0 && (
                  <ul className="ai-reports-bullets">
                    {section.bullets.map((b, i) => (
                      <li key={i}>
                        {b.link_path ? <Link to={b.link_path}>{b.text}</Link> : b.text}
                        {b.metric_value && <span className="crm-muted"> ({b.metric_value})</span>}
                      </li>
                    ))}
                  </ul>
                )}
                {section.watch_items?.length > 0 && (
                  <ul className="ai-reports-watch-list crm-mt">
                    {dedupeWatchItems(section.watch_items).map((w) => (
                      <li key={`${w.severity}-${w.text}-${w.link_path || ""}`}>
                        <span className={severityClass(w.severity)}>{w.severity}</span>
                        <span className="ai-reports-watch-text">
                          {w.link_path ? <Link to={w.link_path}>{w.text}</Link> : w.text}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                <button
                  type="button"
                  className="crm-btn crm-btn-sm crm-btn-outline crm-mt"
                  onClick={() => setExpandedSection((v) => (v === section.id ? null : section.id))}
                >
                  {expandedSection === section.id ? "Hide metrics" : "Metrics used"}
                </button>
                {expandedSection === section.id && (
                  <pre className="ai-reports-metrics crm-mt">{JSON.stringify(section.metrics_json, null, 2)}</pre>
                )}
              </div>
            ))}
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

export default AiInsightRunDetail;
