"""API & App Marketplace module constants."""

INTEGRATION_STATUSES = ("available", "installed", "disabled")
WEBHOOK_STATUSES = ("active", "paused")

INTEGRATION_CATALOG = [
    {
        "integration_key": "razorpay",
        "name": "Razorpay",
        "category": "payments",
        "description": "Accept UPI, cards, and netbanking for invoices and online store.",
        "config_fields": ["key_id", "key_secret", "webhook_secret"],
    },
    {
        "integration_key": "whatsapp_business",
        "name": "WhatsApp Business API",
        "category": "messaging",
        "description": "Send follow-ups and payment links on WhatsApp.",
        "config_fields": ["phone_number_id", "access_token", "business_account_id"],
    },
    {
        "integration_key": "tally",
        "name": "Tally Prime",
        "category": "accounting",
        "description": "Sync vouchers and GST data with Tally.",
        "config_fields": ["company_name", "sync_direction"],
    },
    {
        "integration_key": "zoho_books",
        "name": "Zoho Books",
        "category": "accounting",
        "description": "Import contacts, invoices, and expenses from Zoho Books.",
        "config_fields": ["organization_id", "client_id", "client_secret"],
    },
    {
        "integration_key": "google_sheets",
        "name": "Google Sheets",
        "category": "productivity",
        "description": "Export leads and pipeline snapshots to a shared sheet.",
        "config_fields": ["spreadsheet_id", "sheet_name"],
    },
    {
        "integration_key": "slack",
        "name": "Slack",
        "category": "messaging",
        "description": "Post deal wins, overdue invoices, and approvals to a channel.",
        "config_fields": ["webhook_url", "channel"],
    },
    {
        "integration_key": "custom_webhook",
        "name": "Custom webhook",
        "category": "developer",
        "description": "Receive CRM events on your own HTTPS endpoint.",
        "config_fields": ["endpoint_url", "signing_secret"],
    },
]

DEFAULT_API_SCOPES = ["read:contacts", "read:leads", "read:invoices", "read:products"]

WEBHOOK_EVENT_TYPES = [
    "lead.created",
    "deal.stage_changed",
    "invoice.issued",
    "payment.received",
    "order.confirmed",
]
