from __future__ import annotations

import re
import unicodedata

ORDER_STATUSES = [
    "pending_payment",
    "paid",
    "processing",
    "shipped",
    "delivered",
    "cancelled",
    "returned",
]
PAYMENT_STATUSES = ["unpaid", "paid", "refunded", "partial_refund"]
PAYMENT_METHODS = ["online", "bank_transfer", "cod"]
SHIPPING_METHODS = ["digital", "pickup", "standard", "express"]

# Online services checkout (compliance, registrations, SaaS-style engagements).
STORE_CHECKOUT_MODE = "services"
SERVICE_PAYMENT_METHODS = ["online", "bank_transfer"]
SERVICE_PAYMENT_METHOD_LABELS = {
    "online": "Pay online (UPI / card / net banking)",
    "bank_transfer": "Bank transfer / UPI (against proforma invoice)",
}
STORE_PAYMENT_TERMS = ["due_on_receipt", "milestone_50_50", "net_15"]
STORE_PAYMENT_TERM_LABELS = {
    "due_on_receipt": "100% advance — due on receipt (work starts after payment)",
    "milestone_50_50": "50% advance, 50% on service completion",
    "net_15": "Net 15 days — invoice terms (B2B / GST registered)",
}
SERVICE_SHIPPING_METHODS = ["digital", "pickup"]
SERVICE_SHIPPING_METHOD_LABELS = {
    "digital": "Online service delivery (no physical shipping)",
    "pickup": "In-office consultation / document handover",
}
DEFAULT_SERVICE_PAYMENT_METHOD = "bank_transfer"
DEFAULT_SERVICE_PAYMENT_TERMS = "due_on_receipt"
DEFAULT_SERVICE_SHIPPING_METHOD = "digital"
RETURN_STATUSES = ["requested", "approved", "rejected", "received", "refunded", "closed"]

ORDER_STATUS_LABELS = {
    "pending_payment": "Pending payment",
    "paid": "Paid",
    "processing": "Processing",
    "shipped": "Shipped",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
    "returned": "Returned",
}
PAYMENT_STATUS_LABELS = {
    "unpaid": "Unpaid",
    "paid": "Paid",
    "refunded": "Refunded",
    "partial_refund": "Partial refund",
}
RETURN_STATUS_LABELS = {
    "requested": "Requested",
    "approved": "Approved",
    "rejected": "Rejected",
    "received": "Received",
    "refunded": "Refunded",
    "closed": "Closed",
}

DEFAULT_RETURN_WINDOW_DAYS = 7
DEFAULT_FLAT_SHIPPING = 99
DEFAULT_FREE_SHIPPING_ABOVE = 2000
MAX_CART_QTY = 99
CART_EXPIRY_DAYS = 7
STORE_CONTACT_SOURCE = "Online Store"

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_slug(value: str) -> str:
    text = unicodedata.normalize("NFKD", (value or "").strip().lower())
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:80]


def product_unit_price(product) -> float:
    price = product.offer_price or product.total_price or 0
    return float(price or 0)


def product_online_slug(product) -> str:
    if getattr(product, "online_slug", None):
        return product.online_slug
    return normalize_slug(product.name) or f"product-{product.id}"


# Default shop images when online_image_url is not set (category-themed stock photos).
CATEGORY_PRODUCT_IMAGES = {
    "starting up": "https://images.unsplash.com/photo-1556761175-5973dc0f32e7?w=640&h=480&fit=crop&q=80",
    "compliance": "https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=640&h=480&fit=crop&q=80",
    "taxation": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=640&h=480&fit=crop&q=80",
    "legal": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=640&h=480&fit=crop&q=80",
}

FALLBACK_PRODUCT_IMAGES = [
    "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=640&h=480&fit=crop&q=80",
    "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=640&h=480&fit=crop&q=80",
    "https://images.unsplash.com/photo-1521737711862-ea3e0977328c?w=640&h=480&fit=crop&q=80",
]


def product_display_image_url(product) -> str:
    """Public shop image — uses uploaded URL or a category/default placeholder."""
    if getattr(product, "online_image_url", None):
        return product.online_image_url
    cat = (getattr(product, "category", None) or "").strip().lower()
    if cat in CATEGORY_PRODUCT_IMAGES:
        return CATEGORY_PRODUCT_IMAGES[cat]
    product_id = int(getattr(product, "id", 0) or 0)
    return FALLBACK_PRODUCT_IMAGES[product_id % len(FALLBACK_PRODUCT_IMAGES)]
