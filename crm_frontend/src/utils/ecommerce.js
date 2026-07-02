import { fetchWithNetworkHint, parseApiJson, publicApiPath } from "./api";

export const ORDER_STATUS_LABELS = {
  pending_payment: "Pending payment",
  paid: "Paid",
  processing: "Processing",
  shipped: "Shipped",
  delivered: "Delivered",
  cancelled: "Cancelled",
  returned: "Returned",
};

export const PAYMENT_STATUS_LABELS = {
  unpaid: "Unpaid",
  paid: "Paid",
  refunded: "Refunded",
  partial_refund: "Partial refund",
};

export const RETURN_STATUS_LABELS = {
  requested: "Requested",
  approved: "Approved",
  rejected: "Rejected",
  received: "Received",
  refunded: "Refunded",
  closed: "Closed",
};

export function formatINR(amount) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(amount || 0);
}

function cartSessionKey(slug) {
  return `store_cart_session_${slug}`;
}

function customerTokenKey(slug) {
  return `store_customer_token_${slug}`;
}

export function getCartSession(slug) {
  return localStorage.getItem(cartSessionKey(slug)) || "";
}

export function setCartSession(slug, sessionId) {
  if (sessionId) localStorage.setItem(cartSessionKey(slug), sessionId);
}

export function getStoreCustomerToken(slug) {
  return localStorage.getItem(customerTokenKey(slug)) || "";
}

export function setStoreCustomerToken(slug, token) {
  if (token) localStorage.setItem(customerTokenKey(slug), token);
  else localStorage.removeItem(customerTokenKey(slug));
}

export async function publicShopFetch(slug, path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const session = getCartSession(slug);
  if (session) headers["X-Cart-Session"] = session;
  const token = getStoreCustomerToken(slug);
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetchWithNetworkHint(publicApiPath(`/public/${slug}${path}`), { ...options, headers });
  const data = await parseApiJson(response);
  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
        : `Request failed (${response.status})`;
    throw new Error(message);
  }
  if (data === null) {
    throw new Error("Server returned an invalid response.");
  }
  if (data.session_id) setCartSession(slug, data.session_id);
  return data;
}

export async function fetchShopInfo(slug) {
  return publicShopFetch(slug, "/shop/info");
}

export async function fetchCompanyBranding(slug) {
  const response = await fetchWithNetworkHint(publicApiPath(`/public/${slug}`));
  const data = await parseApiJson(response);
  if (!response.ok) throw new Error(data?.detail || "Site not found");
  if (!data?.company) {
    throw new Error("Site branding data is missing from the server response.");
  }
  return data.company;
}

export function emptyCheckoutForm(overrides = {}) {
  return {
    guest_name: "",
    guest_email: "",
    guest_phone: "",
    gstin: "",
    shipping_address: { line1: "", line2: "", city: "", state: "", pincode: "" },
    billing_same: true,
    billing_address: { line1: "", line2: "", city: "", state: "", pincode: "" },
    shipping_method: "pickup",
    payment_method: "bank_transfer",
    payment_terms: "due_on_receipt",
    customer_note: "",
    ...overrides,
  };
}

export function orderStatusBadgeClass(status) {
  if (status === "delivered" || status === "paid") return "crm-badge crm-badge-success";
  if (status === "cancelled" || status === "returned") return "crm-badge crm-badge-muted";
  if (status === "pending_payment") return "crm-badge crm-badge-warning";
  return "crm-badge crm-badge-info";
}
