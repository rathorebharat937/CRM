export const CAMPAIGN_TYPE_LABELS = {
  drip: "Drip campaign",
  nurture: "Lead nurture",
  reactivation: "Reactivation",
};

export const CAMPAIGN_STATUS_LABELS = {
  draft: "Draft",
  active: "Active",
  paused: "Paused",
  completed: "Completed",
};

export function formatDateTime(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
