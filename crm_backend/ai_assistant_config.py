"""AI Assistant module constants."""

ASSISTANT_ACTIONS = (
    "search_records",
    "draft_email",
    "invoice_help",
    "summarize_stats",
    "create_reminder",
)

DEFAULT_ACTIONS = list(ASSISTANT_ACTIONS)

INTENT_KEYWORDS = {
    "search_records": ("search", "find", "lookup", "show me", "list"),
    "draft_email": ("email", "draft", "write", "message"),
    "invoice_help": ("invoice", "bill", "gst", "billing"),
    "summarize_stats": ("summary", "summarize", "overview", "kpi", "stats", "report"),
    "create_reminder": ("remind", "follow up", "follow-up", "callback"),
}

SUGGESTED_PROMPTS = [
    "Search leads assigned to me",
    "Summarize sales KPIs for this month",
    "Draft a payment reminder email",
    "How do I create a GST invoice?",
    "Remind me to call Acme Corp tomorrow",
]
