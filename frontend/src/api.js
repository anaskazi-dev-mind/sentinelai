/**
 * api.js
 * -------
 * Centralized API client. Every network call in the app goes through
 * this file -- no component ever calls fetch() directly. This means:
 *   - Auth headers, error handling, and the base URL are defined once
 *   - Swapping dev (Vite proxy) vs production (real backend URL) is a
 *     single env var change, not a find-and-replace across components
 *
 * Note: this is a standalone app running in the user's own browser via
 * Vite, not a Claude.ai artifact -- so localStorage is the correct,
 * standard choice here for persisting the JWT across page reloads.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const TOKEN_KEY = "sentinelai_token";

// =====================================================================
// Token storage
// =====================================================================

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// =====================================================================
// Core request wrapper
// =====================================================================

class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, { method = "GET", body, auth = false, isForm = false } = {}) {
  const headers = {};
  if (!isForm) headers["Content-Type"] = "application/json";

  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: isForm ? body : body ? JSON.stringify(body) : undefined,
  });

  let payload = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    payload = await response.json().catch(() => null);
  }

  if (!response.ok) {
    const detail = payload?.detail || response.statusText || "Request failed";
    throw new ApiError(detail, response.status, payload?.detail);
  }

  return payload;
}

// =====================================================================
// Auth
// =====================================================================

export const auth = {
  register: (username, email, password) =>
    request("/auth/register", { method: "POST", body: { username, email, password } }),

  login: async (username, password) => {
    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);

    const data = await request("/auth/login", {
      method: "POST",
      body: form,
      isForm: true,
    });
    setToken(data.access_token);
    return data;
  },

  me: () => request("/auth/me", { auth: true }),

  logout: () => clearToken(),
};

// =====================================================================
// Events (Live Feed, Risk Trend, Clusters)
// =====================================================================

export const events = {
  list: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/events${query ? `?${query}` : ""}`);
  },

  get: (eventId) => request(`/events/${eventId}`),

  triggerScan: () => request("/events/scan", { method: "POST" }),

  riskTrend: (hoursBack = 6) => request(`/events/analytics/risk-trend?hours_back=${hoursBack}`),

  clusters: () => request("/events/analytics/clusters"),
};

// =====================================================================
// Files (Vault)
// =====================================================================

export const files = {
  list: () => request("/files"),

  listBackups: () => request("/files/backups", { auth: true }),

  backup: (path) => request("/files/backup", { method: "POST", body: { path }, auth: true }),

  encrypt: (path) => request("/files/encrypt", { method: "POST", body: { path }, auth: true }),

  decrypt: (fileId) => request(`/files/decrypt/${fileId}`, { method: "POST", auth: true }),
};

// =====================================================================
// Chat (AI Copilot)
// =====================================================================

export const chat = {
  send: (message) => request("/chat", { method: "POST", body: { message }, auth: true }),

  history: (limit = 50) => request(`/chat/history?limit=${limit}`, { auth: true }),
};

export { ApiError };