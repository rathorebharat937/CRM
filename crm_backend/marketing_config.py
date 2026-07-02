"""Marketing Automation module constants."""

CAMPAIGN_TYPES = ("drip", "nurture", "reactivation")
CAMPAIGN_STATUSES = ("draft", "active", "paused", "completed")
AUDIENCE_TYPES = ("leads", "contacts", "both")
ENROLLMENT_STATUSES = ("active", "completed", "unsubscribed", "failed")
SEND_CHANNELS = ("in_app", "reminder", "email_draft")
SEND_STATUSES = ("queued", "sent", "skipped", "failed")

CAMPAIGN_TYPE_LABELS = {
    "drip": "Drip campaign",
    "nurture": "Lead nurture",
    "reactivation": "Reactivation",
}

DEFAULT_CAMPAIGN_PREFIX = "MKT"

CAMPAIGN_TEMPLATES = [
    {
        "name": "New lead welcome sequence",
        "campaign_type": "drip",
        "audience_type": "leads",
        "audience_filter_json": {"lead_status": ["open", "hot", "follow_up"]},
        "description": "Three-touch welcome for fresh enquiries.",
        "steps_json": [
            {
                "delay_days": 0,
                "channel": "reminder",
                "subject": "Welcome — first outreach",
                "body": "Call or WhatsApp the lead within 2 hours. Introduce BlackPapers services.",
            },
            {
                "delay_days": 2,
                "channel": "reminder",
                "subject": "Share service brochure",
                "body": "Send quotation options and ask for a discovery call.",
            },
            {
                "delay_days": 5,
                "channel": "in_app",
                "subject": "Check engagement",
                "body": "Review if the lead opened your message. Escalate to manager if cold.",
            },
        ],
    },
    {
        "name": "Stale lead reactivation",
        "campaign_type": "reactivation",
        "audience_type": "leads",
        "audience_filter_json": {"lead_status": ["lost", "cold"]},
        "description": "Win back leads with no activity in 30+ days.",
        "steps_json": [
            {
                "delay_days": 0,
                "channel": "reminder",
                "subject": "Reactivation call",
                "body": "Offer a limited-time consultation or audit to re-open the conversation.",
            },
            {
                "delay_days": 7,
                "channel": "email_draft",
                "subject": "We miss you — special offer",
                "body": "Draft a short re-engagement email with a clear CTA to book a call.",
            },
        ],
    },
    {
        "name": "Client nurture — quarterly check-in",
        "campaign_type": "nurture",
        "audience_type": "contacts",
        "audience_filter_json": {"contact_type": ["Customer"]},
        "description": "Keep active clients warm between projects.",
        "steps_json": [
            {
                "delay_days": 0,
                "channel": "reminder",
                "subject": "Quarterly check-in",
                "body": "Schedule a 15-minute check-in on ongoing compliance or new service needs.",
            },
        ],
    },
]
