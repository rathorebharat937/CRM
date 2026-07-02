export const DOMAIN_LABELS = {
  sales: "Sales",
  finance: "Finance",
  inventory: "Inventory",
  hr: "HR",
  operations: "Operations",
  executive: "Executive",
};

export const PERIOD_LABELS = {
  "7d": "Last 7 days",
  "30d": "Last 30 days",
  mtd: "Month to date",
  last_month: "Last month",
};

export const PERIOD_OPTIONS = ["7d", "30d", "mtd", "last_month"];

export function severityClass(severity) {
  return `crm-badge crm-ai-severity-${severity || "low"}`;
}

export function formatDate(d) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString();
}

export function formatDateTime(d) {
  if (!d) return "—";
  return new Date(d).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
}

export function formatPeriod(start, end) {
  if (!start || !end) return "—";
  return `${formatDate(start)} – ${formatDate(end)}`;
}

/** Remove duplicate watch items (same text/severity/link) from aggregated lists. */
export function dedupeWatchItems(items = []) {
  const seen = new Set();
  return items.filter((w) => {
    const key = `${w.severity || ""}|${w.text || ""}|${w.link_path || ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
