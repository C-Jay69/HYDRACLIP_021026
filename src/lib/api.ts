/**
 * Tiny fetch wrapper for every dashboard call.
 *
 * All requests go through the Bun dev-server proxy at ``/api`` (see
 * ``src/index.ts``), so the browser never needs to know where the backend
 * actually runs, and the HttpOnly Google callback ticket stays usable.
 *
 * The access token rides in an Authorization header because the backend
 * FastAPI auth is bearer-based; the session pair is stored by
 * ``auth-session.tsx`` and refreshed transparently there.
 */

import { loadStoredSession } from "@/auth-session";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type Page<T> = {
  items?: T[];
  total?: number;
  limit?: number;
  offset?: number;
  has_more?: boolean;
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const stored = loadStoredSession();
  const response = await fetch(`/api${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(stored ? { Authorization: `Bearer ${stored.access_token}` } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail && typeof body.detail === "object") {
        message = JSON.stringify(body.detail);
      }
    } catch {
      // non-JSON error body — keep the generic message
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function listAll<T>(path: string): Promise<T[]> {
  /** Fetch one page-sized window; the dashboards cap rendering anyway. */
  const page = await api<Page<T>>(`${path}${path.includes("?") ? "&" : "?"}limit=50`);
  return Array.isArray(page.items) ? page.items : [];
}
