const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

const ACCESS_KEY = "hydraclip.access_token";
const REFRESH_KEY = "hydraclip.refresh_token";

export class ApiError extends Error {
  constructor(message, status = 0, detail = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function getApiBase() {
  return API_BASE;
}

function isBrowser() {
  return typeof window !== "undefined";
}

export function getAccessToken() {
  return isBrowser() ? window.localStorage.getItem(ACCESS_KEY) : null;
}

export function getRefreshToken() {
  return isBrowser() ? window.localStorage.getItem(REFRESH_KEY) : null;
}

export function setTokens(accessToken, refreshToken) {
  if (!isBrowser()) return;
  if (accessToken) window.localStorage.setItem(ACCESS_KEY, accessToken);
  if (refreshToken) window.localStorage.setItem(REFRESH_KEY, refreshToken);
}

export function clearTokens() {
  if (!isBrowser()) return;
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

export function hasTokens() {
  return Boolean(getAccessToken() || getRefreshToken());
}

function notifyUnauthorized() {
  if (!isBrowser()) return;
  window.dispatchEvent(new Event("hydraclip:unauthorized"));
}

let refreshPromise = null;

async function refreshAccessToken() {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      throw new ApiError("Session expired. Please sign in again.", 401);
    }

    const response = await fetch(`${API_BASE}/api/auth/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      clearTokens();
      notifyUnauthorized();
      throw new ApiError("Session expired. Please sign in again.", 401);
    }

    const data = await response.json();
    setTokens(data.access_token, data.refresh_token);
    return data.access_token;
  })().finally(() => {
    refreshPromise = null;
  });

  return refreshPromise;
}

async function parseError(response) {
  let detail = null;
  let message = `Request failed (${response.status})`;

  try {
    const data = await response.json();
    detail = data;
    if (typeof data?.detail === "string") {
      message = data.detail;
    } else if (Array.isArray(data?.detail)) {
      message = data.detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
    } else if (typeof data?.error === "string") {
      message = data.error;
    } else if (typeof data?.message === "string") {
      message = data.message;
    }
  } catch {
    try {
      const text = await response.text();
      if (text) message = text.slice(0, 300);
    } catch {
      // ignore
    }
  }

  return new ApiError(message, response.status, detail);
}

async function request(
  path,
  { method = "GET", body, auth = true, retry = true, headers: extraHeaders } = {},
) {
  const headers = { ...(extraHeaders || {}) };
  const token = getAccessToken();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let payload = body;
  if (body !== undefined && body !== null && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, { method, headers, body: payload });
  } catch (error) {
    throw new ApiError(
      `Cannot reach the API at ${API_BASE}. Is it running?`,
      0,
      error,
    );
  }

  if (response.status === 401 && auth && retry) {
    try {
      await refreshAccessToken();
    } catch {
      throw new ApiError("Session expired. Please sign in again.", 401);
    }
    return request(path, { method, body, auth, retry: false, headers: extraHeaders });
  }

  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return null;

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();
  return response.text();
}

export const api = {
  // Auth
  login: (email, password) =>
    request("/api/auth/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    }),
  register: (name, email, password) =>
    request("/api/auth/auth/register", {
      method: "POST",
      body: { name, email, password },
      auth: false,
    }),
  logout: () => request("/api/auth/auth/logout", { method: "POST" }),

  // Profile / usage
  profile: () => request("/api/users/users/me"),
  updateProfile: (data) =>
    request("/api/users/users/me", { method: "PUT", body: data }),
  usage: () => request("/api/users/users/me/usage"),
  socialAccounts: () => request("/api/users/users/me/social-accounts"),
  disconnectSocial: (platform) =>
    request(`/api/users/users/me/social-accounts/${platform}`, {
      method: "DELETE",
    }),

  // Videos
  videos: () => request("/api/videos/videos"),
  video: (id) => request(`/api/videos/videos/${id}`),
  generate: (title, topic) =>
    request("/api/videos/videos/generate", {
      method: "POST",
      body: { title, topic },
    }),
  status: (id) => request(`/api/videos/videos/${id}/status`),
  download: (id) => request(`/api/videos/videos/${id}/download`),
  deleteVideo: (id) =>
    request(`/api/videos/videos/${id}`, { method: "DELETE" }),

  // Billing
  plans: () => request("/api/billing/billing/plans", { auth: false }),
  subscription: () => request("/api/billing/billing/subscription"),
  checkout: (planId) =>
    request(
      `/api/billing/billing/checkout?plan_id=${encodeURIComponent(planId)}`,
      { method: "POST" },
    ),
  portal: () => request("/api/billing/billing/portal"),

  // Schedules / publishing
  schedules: () => request("/api/schedules/schedules"),
  createSchedule: (data) =>
    request("/api/schedules/schedules", { method: "POST", body: data }),
  publishNow: (id) =>
    request(`/api/schedules/schedules/${id}/publish-now`, { method: "POST" }),
  published: () => request("/api/publishing/publishing"),

  // Templates / social
  templates: () => request("/api/templates/templates"),
  youtubeConnect: () => request("/api/oauth/oauth/youtube/connect"),

  // Diagnostics
  health: () => request("/api/health/ready", { auth: false }),
};
