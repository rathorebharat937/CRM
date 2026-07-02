import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";
import { hasPermission } from "../utils/permissions";
import {
  PERIOD_LABELS,
  REPORT_ENDPOINTS,
  REPORT_TABS,
  badgeClass,
  buildReportParams,
  canExportPL,
  changeClass,
  exportCsv,
  exportFilename,
  formatCurrency,
  formatDate,
  formatPct,
  profitClass,
} from "../utils/plReports";

function ChangeText({ amount, pct }) {
  if (pct == null && amount === 0) return <span className="crm-muted">—</span>;
  const sign = amount >= 0 ? "+" : "";
  return (
    <span className={changeClass(amount)}>
      {formatPct(pct)} ({sign}{formatCurrency(amount)})
    </span>
  );
}

function DataQualityPanel({ quality }) {
  if (!quality) return null;
  return (
    <div className="crm-pl-quality crm-mt-lg">
      <h3>Data quality</h3>
      <ul className="crm-pl-quality-list">
        <li>Excluded draft invoices: <strong>{quality.excluded_draft_invoices}</strong></li>
        <li>Excluded draft vendor bills: <strong>{quality.excluded_draft_bills}</strong></li>
        <li>Excluded draft expenses: <strong>{quality.excluded_draft_expenses}</strong></li>
        <li>
          Expenses deduplicated (vendor bill linked):{" "}
          <strong>{quality.deduplicated_expense_count}</strong>
          {quality.deduplicated_expense_amount > 0 && (
            <> · {formatCurrency(quality.deduplicated_expense_amount)}</>
          )}
        </li>
        {quality.write_off_total > 0 && (
          <li>Write-offs (informational): <strong>{formatCurrency(quality.write_off_total)}</strong></li>
        )}
        {quality.mixed_currency && (
          <li><span className={badgeClass("linked")}>Mixed currency</span> Totals assume single-currency reporting.</li>
        )}
      </ul>
    </div>
  );
}

function PLReports() {
  const role = localStorage.getItem("role") || "Staff";
  const [tab, setTab] = useState("summary");
  const [period, setPeriod] = useState("month");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const requestIdRef = useRef(0);

  const canExport = canExportPL(hasPermission);
  const currency = data?.company?.currency || "INR";

  const changeTab = (nextTab) => {
    setTab(nextTab);
    setData(null);
    setError("");
    setLoading(true);
    setPage(1);
    setSearch("");
  };

  const load = useCallback(() => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError("");
    const params = buildReportParams(period, dateFrom, dateTo, tab === "summary" ? "" : search, page);
    apiFetch(`${REPORT_ENDPOINTS[tab]}?${params}`)
      .then((result) => {
        if (requestId !== requestIdRef.current) return;
        setData(result);
      })
      .catch((err) => {
        if (requestId !== requestIdRef.current) return;
        setData(null);
        setError(err.message);
      })
      .finally(() => {
        if (requestId !== requestIdRef.current) return;
        setLoading(false);
      });
  }, [tab, period, dateFrom, dateTo, search, page]);

  useEffect(() => {
    load();
  }, [load]);

  const logExport = (reportType, rowCount) => {
    if (!canExport) return;
    apiFetch("/pl-reports/export-log", {
      method: "POST",
      body: JSON.stringify({
        report_type: reportType,
        period,
        period_label: data?.period_label,
        row_count: rowCount,
      }),
    }).catch(() => {});
  };

  const handleExport = async () => {
    if (!data || !canExport) return;
    const headerRows = [
      [data.company?.company_name || ""],
      [`Period: ${data.period_label}`],
      [`From: ${formatDate(data.date_from)}`, `To: ${formatDate(data.date_to)}`],
      [],
    ];

    if (tab === "summary") {
      const rows = (data.statement || []).map((line) => [
        line.label,
        line.current,
        line.previous,
        line.current - line.previous,
      ]);
      exportCsv(
        exportFilename(period, data.period_label),
        ["Line", "Current", "Previous", "Change"],
        rows,
        headerRows,
      );
      logExport("summary", rows.length);
      return;
    }

    let exportData = data;
    if (tab !== "summary") {
      try {
        const params = buildReportParams(period, dateFrom, dateTo, search, 1);
        params.set("per_page", "10000");
        exportData = await apiFetch(`${REPORT_ENDPOINTS[tab]}?${params}`);
      } catch {
        exportData = data;
      }
    }

    if (tab === "revenue") {
      const rows = (exportData.register || []).map((r) => [
        r.invoice_number,
        formatDate(r.issue_date),
        r.client_name,
        r.invoice_type_label,
        r.is_credit_note ? -r.subtotal : r.subtotal,
        r.total_tax,
        r.grand_total,
        r.status_label,
      ]);
      exportCsv(
        exportFilename(period, `${data.period_label}-revenue`),
        ["Invoice #", "Date", "Customer", "Type", "Subtotal", "Tax", "Total", "Status"],
        rows,
        headerRows,
      );
      logExport("revenue", rows.length);
      return;
    }

    if (tab === "costs") {
      const rows = (exportData.register || []).map((r) => [
        r.bill_number,
        r.supplier_invoice_number || "",
        formatDate(r.bill_date),
        r.vendor_name,
        r.subtotal,
        r.total_tax,
        r.grand_total,
        r.status_label,
        r.po_number || "",
      ]);
      exportCsv(
        exportFilename(period, `${data.period_label}-costs`),
        ["Bill #", "Supplier invoice #", "Date", "Vendor", "Subtotal", "Tax", "Total", "Status", "PO"],
        rows,
        headerRows,
      );
      logExport("costs", rows.length);
      return;
    }

    if (tab === "expenses") {
      const rows = (exportData.register || []).map((r) => [
        r.expense_number,
        formatDate(r.expense_date),
        r.category_label,
        r.title,
        r.vendor_name,
        r.amount,
        r.status_label,
      ]);
      exportCsv(
        exportFilename(period, `${data.period_label}-expenses`),
        ["Expense #", "Date", "Category", "Title", "Vendor", "Amount", "Status"],
        rows,
        headerRows,
      );
      logExport("expenses", rows.length);
    }
  };

  const totalPages = data?.register_total
    ? Math.max(1, Math.ceil(data.register_total / (data.register_per_page || 50)))
    : 1;

  return (
    <DashboardLayout title="P&L Reports" roleLabel={role}>
      <div className="crm-panel">
        <p className="crm-muted">
          Management profit &amp; loss by period — revenue, purchases, expenses, and net profit.
          For tax compliance see <Link to="/tax-reports" className="crm-nav-link">GST / Tax Reports</Link>.
        </p>

        <div className="crm-tabs crm-mt">
          {REPORT_TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={`crm-tab${tab === t.key ? " crm-tab-active" : ""}`}
              onClick={() => changeTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="crm-filters crm-mt">
          <select value={period} onChange={(e) => { setPeriod(e.target.value); setPage(1); }}>
            {Object.entries(PERIOD_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          {period === "custom" && (
            <>
              <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
              <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
              <button type="button" className="crm-btn crm-btn-sm" onClick={load}>Apply</button>
            </>
          )}
          {tab !== "summary" && (
            <>
              <input
                type="search"
                placeholder="Search…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (setPage(1), load())}
              />
              <button type="button" className="crm-btn crm-btn-sm" onClick={() => { setPage(1); load(); }}>Search</button>
            </>
          )}
          {canExport && (
            <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={handleExport} disabled={!data}>
              Export CSV
            </button>
          )}
        </div>

        {error && <p className="crm-error crm-mt">{error}</p>}
        {loading && <p className="crm-muted crm-mt">Loading report…</p>}

        {!loading && data && tab === "summary" && (
          <>
            <p className="crm-muted crm-mt-sm">
              {data.period_label} · {formatDate(data.date_from)} – {formatDate(data.date_to)}
              {data.comparison_period_label && <> · Compared to {data.comparison_period_label}</>}
            </p>

            <div className="crm-stats-grid crm-mt">
              <div className="crm-stat-card crm-pl-card-revenue">
                <p className="crm-stat-label">Net revenue</p>
                <p className="crm-stat-value">{formatCurrency(data.net_revenue, currency)}</p>
                {data.comparisons?.find((c) => c.key === "net_revenue") && (
                  <p className="crm-stat-sub">
                    <ChangeText {...data.comparisons.find((c) => c.key === "net_revenue")} amount={data.comparisons.find((c) => c.key === "net_revenue").change_amount} pct={data.comparisons.find((c) => c.key === "net_revenue").change_pct} />
                  </p>
                )}
              </div>
              <div className="crm-stat-card crm-pl-card-cost">
                <p className="crm-stat-label">Purchases / direct costs</p>
                <p className="crm-stat-value">{formatCurrency(data.purchases_costs, currency)}</p>
              </div>
              <div className="crm-stat-card crm-pl-card-gross">
                <p className="crm-stat-label">Gross profit</p>
                <p className={`crm-stat-value ${profitClass(data.gross_profit)}`}>{formatCurrency(data.gross_profit, currency)}</p>
                {data.gross_margin_pct != null && <p className="crm-stat-sub">Margin {formatPct(data.gross_margin_pct)}</p>}
              </div>
              <div className="crm-stat-card crm-pl-card-expense">
                <p className="crm-stat-label">Operating expenses</p>
                <p className="crm-stat-value">{formatCurrency(data.operating_expenses, currency)}</p>
              </div>
              <div className="crm-stat-card crm-pl-card-net">
                <p className="crm-stat-label">Net profit</p>
                <p className={`crm-stat-value ${profitClass(data.net_profit)}`}>{formatCurrency(data.net_profit, currency)}</p>
                {data.net_margin_pct != null && <p className="crm-stat-sub">Margin {formatPct(data.net_margin_pct)}</p>}
                {data.comparisons?.find((c) => c.key === "net_profit") && (
                  <p className="crm-stat-sub">
                    <ChangeText {...data.comparisons.find((c) => c.key === "net_profit")} amount={data.comparisons.find((c) => c.key === "net_profit").change_amount} pct={data.comparisons.find((c) => c.key === "net_profit").change_pct} />
                  </p>
                )}
              </div>
            </div>

            <p className="crm-muted crm-mt-sm">Management P&L for review — not statutory audited accounts. Amounts exclude GST.</p>

            <h3 className="crm-mt-lg">Income statement</h3>
            <div className="crm-table-wrap">
              <table className="crm-table">
                <thead>
                  <tr>
                    <th>Line</th>
                    <th className="crm-num">Current</th>
                    <th className="crm-num">Previous</th>
                    <th className="crm-num">Change</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.statement || []).map((line) => (
                    <tr key={line.key} className={line.is_total ? "crm-pl-statement-total" : ""}>
                      <td>{line.is_total ? <strong>{line.label}</strong> : line.label}</td>
                      <td className={`crm-num ${line.is_total ? profitClass(line.current) : ""}`}>{formatCurrency(line.current, currency)}</td>
                      <td className={`crm-num ${line.is_total ? profitClass(line.previous) : ""}`}>{formatCurrency(line.previous, currency)}</td>
                      <td className="crm-num">
                        <ChangeText amount={line.current - line.previous} pct={line.previous ? ((line.current - line.previous) / Math.abs(line.previous)) * 100 : null} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {data.expense_categories?.length > 0 && (
              <>
                <h3 className="crm-mt-lg">Operating expenses by category</h3>
                <div className="crm-stats-grid crm-mt-sm">
                  {data.expense_categories.map((c) => (
                    <div key={c.category} className="crm-stat-card">
                      <p className="crm-stat-label">{c.category_label}</p>
                      <p className="crm-stat-value">{formatCurrency(c.amount, currency)}</p>
                    </div>
                  ))}
                </div>
              </>
            )}

            {data.trend?.length > 0 && (
              <>
                <h3 className="crm-mt-lg">Trend (last 6 months)</h3>
                <div className="crm-table-wrap">
                  <table className="crm-table">
                    <thead>
                      <tr>
                        <th>Month</th>
                        <th className="crm-num">Net revenue</th>
                        <th className="crm-num">Gross profit</th>
                        <th className="crm-num">Net profit</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.trend.map((t) => (
                        <tr key={t.period_label}>
                          <td>{t.period_label}</td>
                          <td className="crm-num">{formatCurrency(t.net_revenue, currency)}</td>
                          <td className={`crm-num ${profitClass(t.gross_profit)}`}>{formatCurrency(t.gross_profit, currency)}</td>
                          <td className={`crm-num ${profitClass(t.net_profit)}`}>{formatCurrency(t.net_profit, currency)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            <DataQualityPanel quality={data.data_quality} />
          </>
        )}

        {!loading && data && tab === "revenue" && (
          <>
            <div className="crm-stats-grid crm-mt">
              <div className="crm-stat-card"><p className="crm-stat-label">Gross sales</p><p className="crm-stat-value">{formatCurrency(data.gross_sales, currency)}</p></div>
              <div className="crm-stat-card"><p className="crm-stat-label">Credit notes</p><p className="crm-stat-value">{formatCurrency(data.credit_notes, currency)}</p></div>
              <div className="crm-stat-card crm-pl-card-revenue"><p className="crm-stat-label">Net revenue</p><p className="crm-stat-value">{formatCurrency(data.net_revenue, currency)}</p></div>
            </div>
            <div className="crm-table-wrap crm-mt">
              <table className="crm-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Invoice #</th>
                    <th>Customer</th>
                    <th>Type</th>
                    <th className="crm-num">Subtotal</th>
                    <th className="crm-num">Tax</th>
                    <th className="crm-num">Total</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.register.length === 0 && <tr><td colSpan={9} className="crm-muted">No revenue documents in this period.</td></tr>}
                  {data.register.map((r) => (
                    <tr key={r.id}>
                      <td>{formatDate(r.issue_date)}</td>
                      <td>{r.invoice_number || "—"}</td>
                      <td>{r.client_name || "—"}</td>
                      <td>
                        <span className={badgeClass(r.is_credit_note ? "credit" : "revenue")}>{r.invoice_type_label}</span>
                      </td>
                      <td className="crm-num">{formatCurrency(r.is_credit_note ? -r.subtotal : r.subtotal, currency)}</td>
                      <td className="crm-num">{formatCurrency(r.total_tax, currency)}</td>
                      <td className="crm-num">{formatCurrency(r.grand_total, currency)}</td>
                      <td>{r.status_label}</td>
                      <td><Link to={`/invoices/${r.id}`} className="crm-nav-link">View</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {totalPages > 1 && (
              <div className="crm-pagination crm-mt">
                <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
                <span className="crm-muted">Page {page} of {totalPages}</span>
                <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</button>
              </div>
            )}
            <DataQualityPanel quality={data.data_quality} />
          </>
        )}

        {!loading && data && tab === "costs" && (
          <>
            <div className="crm-stats-grid crm-mt">
              <div className="crm-stat-card crm-pl-card-cost">
                <p className="crm-stat-label">Purchases / direct costs</p>
                <p className="crm-stat-value">{formatCurrency(data.purchases_costs, currency)}</p>
              </div>
            </div>
            <div className="crm-table-wrap crm-mt">
              <table className="crm-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Bill #</th>
                    <th>Vendor</th>
                    <th>Supplier inv.</th>
                    <th className="crm-num">Subtotal</th>
                    <th className="crm-num">Tax</th>
                    <th className="crm-num">Total</th>
                    <th>Status</th>
                    <th>PO</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.register.length === 0 && <tr><td colSpan={10} className="crm-muted">No purchase bills in this period.</td></tr>}
                  {data.register.map((r) => (
                    <tr key={r.id}>
                      <td>{formatDate(r.bill_date)}</td>
                      <td>{r.bill_number || "—"}</td>
                      <td>{r.vendor_name}</td>
                      <td>{r.supplier_invoice_number || "—"}</td>
                      <td className="crm-num">{formatCurrency(r.subtotal, currency)}</td>
                      <td className="crm-num">{formatCurrency(r.total_tax, currency)}</td>
                      <td className="crm-num">{formatCurrency(r.grand_total, currency)}</td>
                      <td>{r.status_label}{r.expense_linked && <span className={badgeClass("linked")}>Expense linked</span>}</td>
                      <td>{r.purchase_order_id ? <Link to={`/purchase-orders/${r.purchase_order_id}`} className="crm-nav-link">{r.po_number || "PO"}</Link> : "—"}</td>
                      <td><Link to={`/vendor-bills/${r.id}`} className="crm-nav-link">View</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {totalPages > 1 && (
              <div className="crm-pagination crm-mt">
                <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
                <span className="crm-muted">Page {page} of {totalPages}</span>
                <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</button>
              </div>
            )}
            <DataQualityPanel quality={data.data_quality} />
          </>
        )}

        {!loading && data && tab === "expenses" && (
          <>
            <div className="crm-stats-grid crm-mt">
              <div className="crm-stat-card crm-pl-card-expense">
                <p className="crm-stat-label">Operating expenses</p>
                <p className="crm-stat-value">{formatCurrency(data.operating_expenses, currency)}</p>
              </div>
            </div>
            {data.expense_categories?.length > 0 && (
              <div className="crm-stats-grid crm-mt-sm">
                {data.expense_categories.map((c) => (
                  <div key={c.category} className="crm-stat-card">
                    <p className="crm-stat-label">{c.category_label}</p>
                    <p className="crm-stat-value">{formatCurrency(c.amount, currency)}</p>
                  </div>
                ))}
              </div>
            )}
            <div className="crm-table-wrap crm-mt">
              <table className="crm-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Expense #</th>
                    <th>Category</th>
                    <th>Title</th>
                    <th>Vendor</th>
                    <th className="crm-num">Amount</th>
                    <th>Status</th>
                    <th>Submitter</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.register.length === 0 && <tr><td colSpan={9} className="crm-muted">No operating expenses in this period.</td></tr>}
                  {data.register.map((r) => (
                    <tr key={r.id}>
                      <td>{formatDate(r.expense_date)}</td>
                      <td>{r.expense_number || "—"}</td>
                      <td><span className={badgeClass("expense")}>{r.category_label}</span></td>
                      <td>{r.title}</td>
                      <td>{r.vendor_name}</td>
                      <td className="crm-num">{formatCurrency(r.amount, currency)}</td>
                      <td>{r.status_label}</td>
                      <td>{r.submitter_name || "—"}</td>
                      <td><Link to={`/expenses/${r.id}`} className="crm-nav-link">View</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data.excluded_duplicates?.length > 0 && (
              <>
                <h3 className="crm-mt-lg">Excluded duplicates (vendor bill linked)</h3>
                <div className="crm-table-wrap">
                  <table className="crm-table">
                    <thead>
                      <tr><th>Date</th><th>Expense #</th><th>Title</th><th>Vendor</th><th className="crm-num">Amount</th><th>Reason</th></tr>
                    </thead>
                    <tbody>
                      {data.excluded_duplicates.map((r) => (
                        <tr key={r.id}>
                          <td>{formatDate(r.expense_date)}</td>
                          <td>{r.expense_number || "—"}</td>
                          <td>{r.title}</td>
                          <td>{r.vendor_name}</td>
                          <td className="crm-num">{formatCurrency(r.amount, currency)}</td>
                          <td>{r.exclusion_reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
            {totalPages > 1 && (
              <div className="crm-pagination crm-mt">
                <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
                <span className="crm-muted">Page {page} of {totalPages}</span>
                <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</button>
              </div>
            )}
            <DataQualityPanel quality={data.data_quality} />
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

export default PLReports;
