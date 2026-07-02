import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";
import {
  DOMAIN_LABELS,
  PERIOD_LABELS,
  PERIOD_OPTIONS,
  dedupeWatchItems,
  formatDateTime,
  formatPeriod,
  severityClass,
} from "../utils/aiReports";
import { hasPermission } from "../utils/permissions";

function AiReportsHub() {
  const role = localStorage.getItem("role") || "Staff";
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [settings, setSettings] = useState(null);
  const [permittedDomains, setPermittedDomains] = useState([]);
  const [activeDomain, setActiveDomain] = useState("sales");
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [period, setPeriod] = useState("30d");
  const [selectedDomains, setSelectedDomains] = useState([]);
  const [includeExecutive, setIncludeExecutive] = useState(true);
  const [latestRun, setLatestRun] = useState(null);

  const canGenerate = hasPermission("ai_reports.generate");

  const load = async () => {
    const [dash, domains, cfg] = await Promise.all([
      apiFetch("/ai-reports/dashboard"),
      apiFetch("/ai-reports/domains"),
      apiFetch("/ai-reports/settings"),
    ]);
    setDashboard(dash);
    setPermittedDomains(domains.domains || []);
    setSettings(cfg);
    setPeriod(cfg.default_period || "30d");
    setSelectedDomains(
      (cfg.default_domains_json || []).filter((d) => (domains.domains || []).includes(d))
    );
    setIncludeExecutive(cfg.include_executive_brief !== false);
    if (dash.latest_run?.id) {
      const run = await apiFetch(`/ai-reports/runs/${dash.latest_run.id}`);
      setLatestRun(run);
      if (run.sections?.length) {
        const first = run.sections.find((s) => s.domain !== "executive") || run.sections[0];
        setActiveDomain(first.domain);
      }
    } else {
      setLatestRun(null);
    }
  };

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  const watchItems = useMemo(
    () => dedupeWatchItems(dashboard?.watch_items || []),
    [dashboard?.watch_items]
  );

  const activeSection = useMemo(
    () => latestRun?.sections?.find((s) => s.domain === activeDomain),
    [latestRun, activeDomain]
  );

  const domainTabs = useMemo(() => {
    if (!latestRun?.sections) return [];
    return latestRun.sections.filter((s) => s.domain !== "executive");
  }, [latestRun]);

  const toggleDomain = (domain) => {
    setSelectedDomains((prev) =>
      prev.includes(domain) ? prev.filter((d) => d !== domain) : [...prev, domain]
    );
  };

  const generate = async (e) => {
    e.preventDefault();
    if (!canGenerate || selectedDomains.length === 0) return;
    setGenerating(true);
    setError("");
    try {
      const run = await apiFetch("/ai-reports/generate", {
        method: "POST",
        body: JSON.stringify({
          period,
          domains: selectedDomains,
          include_executive_brief: includeExecutive,
        }),
      });
      await load();
      navigate(`/ai-reports/runs/${run.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <DashboardLayout title="AI Reports" roleLabel={role}>
      <div className="crm-panel">
        <div className="crm-detail-header">
          <p className="crm-muted">Plain-language insights across sales, finance, inventory, HR, and operations</p>
          <div className="crm-inline-actions">
            {hasPermission("ai_reports.manage_settings") && (
              <Link to="/ai-reports/settings" className="crm-btn crm-btn-sm crm-btn-outline">Settings</Link>
            )}
          </div>
        </div>

        {error && <p className="crm-error crm-mt">{error}</p>}

        {settings && !settings.is_enabled && (
          <p className="crm-muted crm-mt">AI Reports is disabled. Enable it in settings to generate briefs.</p>
        )}

        {canGenerate && settings?.is_enabled && (
          <form className="crm-form crm-mt ai-reports-generate-card" onSubmit={generate}>
            <h3>Generate insight brief</h3>
            <div className="crm-form-row">
              <div className="crm-form-field">
                <label>Period</label>
                <select value={period} onChange={(e) => setPeriod(e.target.value)}>
                  {PERIOD_OPTIONS.map((p) => (
                    <option key={p} value={p}>{PERIOD_LABELS[p]}</option>
                  ))}
                </select>
              </div>
              <div className="crm-form-field">
                <label>Domains</label>
                <div className="crm-checkbox-group">
                  {permittedDomains.map((d) => (
                    <label key={d}>
                      <input
                        type="checkbox"
                        checked={selectedDomains.includes(d)}
                        onChange={() => toggleDomain(d)}
                      />
                      {" "}{DOMAIN_LABELS[d] || d}
                    </label>
                  ))}
                </div>
              </div>
            </div>
            <div className="crm-form-field">
              <label>
                <input
                  type="checkbox"
                  checked={includeExecutive}
                  onChange={(e) => setIncludeExecutive(e.target.checked)}
                />
                {" "}Include executive brief
              </label>
            </div>
            <button type="submit" className="crm-btn crm-btn-inline ai-reports-generate-btn" disabled={generating || selectedDomains.length === 0}>
              {generating ? "Generating…" : "Generate"}
            </button>
          </form>
        )}

        {latestRun ? (
          <div className="crm-mt ai-reports-layout">
            <div className="ai-reports-main">
              <div className="ai-reports-headline">
                <span className="crm-muted">{latestRun.run_number} · {formatPeriod(latestRun.period_start, latestRun.period_end)}</span>
                <h2>{latestRun.executive_headline || "Insight brief"}</h2>
                {latestRun.executive_summary && <p>{latestRun.executive_summary}</p>}
                <Link to={`/ai-reports/runs/${latestRun.id}`} className="crm-btn crm-btn-sm crm-btn-outline crm-mt">
                  View full brief
                </Link>
              </div>

              {domainTabs.length > 0 && (
                <>
                  <div className="crm-tabs crm-mt">
                    {domainTabs.map((s) => (
                      <button
                        key={s.domain}
                        type="button"
                        className={`crm-tab ${activeDomain === s.domain ? "crm-tab-active" : ""}`}
                        onClick={() => setActiveDomain(s.domain)}
                      >
                        {DOMAIN_LABELS[s.domain] || s.domain}
                      </button>
                    ))}
                  </div>
                  {activeSection && (
                    <div className="ai-reports-domain-panel">
                      <h3>{activeSection.headline}</h3>
                      <p>{activeSection.narrative}</p>
                      {activeSection.bullets?.length > 0 && (
                        <ul className="ai-reports-bullets">
                          {activeSection.bullets.map((b, i) => (
                            <li key={i}>
                              {b.link_path ? <Link to={b.link_path}>{b.text}</Link> : b.text}
                              {b.metric_value && <span className="crm-muted"> ({b.metric_value})</span>}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>

            <aside className="ai-reports-sidebar">
              <h3>Watch items</h3>
              {watchItems.length === 0 ? (
                <p className="crm-muted">No watch items for this brief.</p>
              ) : (
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
              )}
            </aside>
          </div>
        ) : (
          dashboard && (
            <p className="crm-muted crm-mt">No insight brief yet. Generate your first brief to see narratives and watch items.</p>
          )
        )}

        {dashboard?.recent_runs?.length > 0 && (
          <section className="ai-reports-recent crm-mt">
            <h3>Recent runs</h3>
            <table className="crm-table crm-mt">
              <thead>
                <tr>
                  <th>Run #</th>
                  <th>Period</th>
                  <th>Domains</th>
                  <th>Status</th>
                  <th>Headline</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {dashboard.recent_runs.map((r) => (
                  <tr key={r.id}>
                    <td><Link to={`/ai-reports/runs/${r.id}`}>{r.run_number}</Link></td>
                    <td>{formatPeriod(r.period_start, r.period_end)}</td>
                    <td>{(r.domains_json || []).map((d) => DOMAIN_LABELS[d] || d).join(", ")}</td>
                    <td>{r.status}</td>
                    <td>{r.executive_headline || "—"}</td>
                    <td>{formatDateTime(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </div>
    </DashboardLayout>
  );
}

export default AiReportsHub;
