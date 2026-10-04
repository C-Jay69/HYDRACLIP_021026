/**
 * Regression tests for the persisted auth session.
 *
 * Bug being pinned down: AuthPage stored the login tokens in localStorage, but
 * nothing ever read them back — the landing header unconditionally rendered
 * "Sign in / Get started", so a signed-in user returning to the landing page
 * was prompted to log in again and the flow looked like an endless loop.
 *
 * These tests render the header (and the whole landing page) through
 * AuthSessionProvider with a stored session and assert the signed-in UI.
 * Effects do not run under renderToStaticMarkup, so these exercise the
 * synchronous restore path — which is exactly what must not flash the wrong
 * state on the very first paint.
 */
import { beforeEach, describe, expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";

import {
  AuthSessionProvider,
  clearSession,
  loadStoredSession,
  saveSession,
  SESSION_KEY,
} from "@/auth-session";
import { AuthPage } from "@/components/AuthPage";
import { DashboardPage } from "@/components/DashboardPage";
import { LandingPage } from "@/components/landing/LandingPage";
import { SiteHeader } from "@/components/landing/SiteHeader";

/** Deterministic in-memory localStorage, installed before any render. */
function createStorage(): Storage {
  const map = new Map<string, string>();
  return {
    get length() {
      return map.size;
    },
    clear: () => map.clear(),
    getItem: (key: string) => map.get(key) ?? null,
    key: (index: number) => [...map.keys()][index] ?? null,
    removeItem: (key: string) => void map.delete(key),
    setItem: (key: string, value: string) => void map.set(key, String(value)),
  };
}

Object.defineProperty(globalThis, "localStorage", {
  value: createStorage(),
  configurable: true,
  writable: true,
});

// AuthPage reads window.location.search during render; supply the minimal
// shape that code path needs (effects never run under renderToStaticMarkup).
if (typeof window === "undefined") {
  Object.defineProperty(globalThis, "window", {
    value: { location: { search: "" } },
    configurable: true,
    writable: true,
  });
}

const DEMO_USER = { id: 7, email: "ada@example.com", name: "Ada Lovelace" };

function storeDemoSession() {
  saveSession({
    access_token: "demo-access-token",
    refresh_token: "demo-refresh-token",
    expires_in: 3600,
    user: DEMO_USER,
  });
}

function renderHeader(): string {
  return renderToStaticMarkup(
    <AuthSessionProvider>
      <SiteHeader />
    </AuthSessionProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
});

describe("session storage helpers", () => {
  test("saveSession persists the pair with an absolute expiry", () => {
    const before = Date.now();
    saveSession({
      access_token: "a",
      refresh_token: "r",
      expires_in: 3600,
      user: DEMO_USER,
    });

    const stored = loadStoredSession();
    expect(stored).not.toBeNull();
    expect(stored?.access_token).toBe("a");
    expect(stored?.refresh_token).toBe("r");
    expect(stored?.user.email).toBe(DEMO_USER.email);
    expect(stored?.expires_at).toBeNumber();
    // ~1 hour from now, allowing for execution time.
    expect(stored?.expires_at ?? 0).toBeGreaterThan(before + 3590 * 1000);
  });

  test("loads legacy sessions that predate expires_at", () => {
    // The shape AuthPage used to write: raw TokenPair, no absolute expiry.
    localStorage.setItem(
      SESSION_KEY,
      JSON.stringify({
        access_token: "legacy-a",
        refresh_token: "legacy-r",
        expires_in: 3600,
        user: DEMO_USER,
      }),
    );

    const stored = loadStoredSession();
    expect(stored).not.toBeNull();
    expect(stored?.access_token).toBe("legacy-a");
    // Unknown expiry is null so the session is validated against the API.
    expect(stored?.expires_at).toBeNull();
  });

  test("rejects malformed entries instead of throwing", () => {
    localStorage.setItem(SESSION_KEY, "{not json");
    expect(loadStoredSession()).toBeNull();

    localStorage.setItem(SESSION_KEY, JSON.stringify({ user: DEMO_USER }));
    expect(loadStoredSession()).toBeNull();

    localStorage.setItem(
      SESSION_KEY,
      JSON.stringify({ access_token: "a", refresh_token: "r", user: { name: "No email" } }),
    );
    expect(loadStoredSession()).toBeNull();
  });

  test("clearSession removes the persisted session", () => {
    storeDemoSession();
    expect(loadStoredSession()).not.toBeNull();
    clearSession();
    expect(loadStoredSession()).toBeNull();
  });
});

describe("site header reflects the persisted session", () => {
  test("signed-in visitors see identity, Dashboard and Sign out, not login prompts", () => {
    storeDemoSession();
    const html = renderHeader();

    expect(html).toContain("Ada Lovelace");
    expect(html).toContain("Sign out");
    expect(html).toContain('href="/dashboard"');
    expect(html).not.toContain("Sign in");
    expect(html).not.toContain("Get started");
    expect(html).not.toContain('href="/auth"');
    expect(html).not.toContain('href="/auth?mode=signup"');
  });

  test("falls back to the email when the profile has no name", () => {
    saveSession({
      access_token: "a",
      refresh_token: "r",
      expires_in: 3600,
      user: { email: "noname@example.com" },
    });
    const html = renderHeader();

    expect(html).toContain("noname@example.com");
    expect(html).toContain("Sign out");
  });

  test("anonymous visitors see Sign in and Get started", () => {
    const html = renderHeader();

    expect(html).toContain("Sign in");
    expect(html).toContain("Get started");
    expect(html).toContain('href="/auth"');
    expect(html).toContain('href="/auth?mode=signup"');
    expect(html).not.toContain("Sign out");
  });

  test("a corrupted stored session renders as anonymous", () => {
    localStorage.setItem(SESSION_KEY, "\u0000 garbage");
    const html = renderHeader();

    expect(html).toContain("Sign in");
    expect(html).not.toContain("Sign out");
  });
});

describe("landing page regression: no login prompt when signed in", () => {
  test("the rendered landing page shows the signed-in identity", () => {
    storeDemoSession();
    const html = renderToStaticMarkup(
      <AuthSessionProvider>
        <LandingPage />
      </AuthSessionProvider>,
    );

    expect(html).toContain("Ada Lovelace");
    expect(html).toContain("Sign out");
  });

  test("without a session the landing header prompts for login", () => {
    const html = renderToStaticMarkup(
      <AuthSessionProvider>
        <LandingPage />
      </AuthSessionProvider>,
    );

    expect(html).toContain("Sign in");
    expect(html).toContain("Get started");
    expect(html).not.toContain("Sign out");
  });

  test("signed-in visitors are funnelled to the dashboard, never back to /auth", () => {
    storeDemoSession();
    const html = renderToStaticMarkup(
      <AuthSessionProvider>
        <LandingPage />
      </AuthSessionProvider>,
    );

    // Hero, pricing, the bottom CTA and the header must route a signed-in user
    // to the app — never to the login form or account-creation again.
    expect(html).not.toContain("mode=signup");
    expect(html).not.toContain('href="/auth"');
    expect(html).toContain('href="/dashboard"');
    expect(html).toContain("Open your dashboard");
  });
});

describe("auth page respects an existing session", () => {
  test("a signed-in visitor is greeted, not asked for credentials", () => {
    storeDemoSession();
    const html = renderToStaticMarkup(
      <AuthSessionProvider>
        <AuthPage />
      </AuthSessionProvider>,
    );

    expect(html).toContain("Signed in as ada@example.com");
    expect(html).toContain("Continue to HydraClip");
    expect(html).toContain('href="/dashboard"');
    expect(html).toContain("Use a different account");
    expect(html).not.toContain('type="password"');
  });

  test("an anonymous visitor still gets the login and signup tabs", () => {
    const html = renderToStaticMarkup(
      <AuthSessionProvider>
        <AuthPage />
      </AuthSessionProvider>,
    );

    expect(html).not.toContain("Signed in as");
    expect(html).not.toContain("Use a different account");
    expect(html).toContain("Sign in");
    expect(html).toContain("Create account");
  });
});

describe("dashboard page: the destination that ends the landing/auth loop", () => {
  test("signed-in users get a personalised workspace with the media library", () => {
    storeDemoSession();
    const html = renderToStaticMarkup(
      <AuthSessionProvider>
        <DashboardPage />
      </AuthSessionProvider>,
    );

    expect(html).toContain("Welcome back");
    expect(html).toContain("Ada Lovelace");
    expect(html).toContain("Sign out");
    expect(html).toContain('id="dashboard-media"');
    expect(html).not.toContain("You’re not signed in");
  });

  test("anonymous visitors get a guard card pointing to sign in, not the app", () => {
    const html = renderToStaticMarkup(
      <AuthSessionProvider>
        <DashboardPage />
      </AuthSessionProvider>,
    );

    expect(html).toContain("You’re not signed in");
    expect(html).toContain('href="/auth"');
    expect(html).not.toContain('id="dashboard-media"');
    expect(html).not.toContain("Welcome back");
  });
});
