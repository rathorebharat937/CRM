import { clearPermissions, setPermissions } from "./permissions";

/** Backend base URL. In dev, call port 8000 directly (CORS allowed in main.py). */
function resolveApiUrl() {
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL.replace(/\/$/, "");
  }
  if (process.env.NODE_ENV === "development") {
    return "http://localhost:8000";
  }
  if (typeof window !== "undefined" && window.location?.hostname) {
    return `http://${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

/** Public site + shop — same backend URL as CRM (no dev proxy; avoids HTML 404 pages). */
function resolvePublicApiUrl() {
  if (process.env.REACT_APP_PUBLIC_API_URL) {
    return process.env.REACT_APP_PUBLIC_API_URL.replace(/\/$/, "");
  }
  return resolveApiUrl();
}

export const API_URL = resolveApiUrl();
export const PUBLIC_API_URL = resolvePublicApiUrl();

/** Build a URL for public site / shop API. */
export function publicApiPath(path) {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${PUBLIC_API_URL}${suffix}`;
}

/** Parse JSON from a fetch response; detect HTML error pages from a misconfigured proxy. */
export async function parseApiJson(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    if (text.trimStart().startsWith("<")) {
      throw new Error("Server returned a web page instead of API data. Is the backend running on port 8000?");
    }
    return null;
  }
}

export async function fetchWithNetworkHint(url, options) {
  try {
    return await fetch(url, options);
  } catch {
    const proxied = !url.startsWith("http");
    throw new Error(
      proxied
        ? "Cannot reach the server. Restart npm start, then ensure the backend is running on port 8000."
        : "Cannot reach the server. Make sure the backend is running on port 8000.",
    );
  }
}

export function getAuthHeaders() {
  const token = localStorage.getItem("token");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export function saveSession(data) {
  localStorage.setItem("token", data.access_token);
  localStorage.setItem("role", data.role);
  localStorage.setItem("name", data.name);
  localStorage.setItem("email", data.email);
  setPermissions(data.permissions || []);
}

export function clearSession() {
  localStorage.removeItem("token");
  localStorage.removeItem("role");
  localStorage.removeItem("name");
  localStorage.removeItem("email");
  clearPermissions();
}

export async function loginRequest(email, password) {
  const response = await fetchWithNetworkHint(`${API_URL}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message = data.detail || "Login failed. Check your email and password.";
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }

  return data;
}

export async function apiFetch(path, options = {}) {
  const authHeaders = getAuthHeaders();
  if (options.body instanceof FormData) {
    delete authHeaders["Content-Type"];
  }
  const response = await fetchWithNetworkHint(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...authHeaders,
      ...options.headers,
    },
  });

  const data = await response.json().catch(() => null);

  if (data === null) {
    if (response.ok) {
      throw new Error("Server returned an invalid response. Check that the backend is running on port 8000.");
    }
  }

  if (!response.ok) {
    const message = (data && data.detail) || `Request failed (${response.status})`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }

  return data ?? {};
}
