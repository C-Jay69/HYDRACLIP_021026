/**
 * Client-side authentication session.
 *
 * AuthPage persists the token pair returned by the API under SESSION_KEY in
 * localStorage, but before this module existed nothing else ever read it back:
 * the landing header always rendered "Sign in / Get started" even for a
 * signed-in user, which looked like the login flow was looping.
 *
 * This provider restores that persisted session on every page load,
 * synchronously (so the header never flashes the wrong state), then validates
 * it against `/api/auth/me` in an effect:
 *
 *   - access token expired or rejected (401)  → exchange the refresh token
 *     via `/api/auth/refresh` and retry once;
 *   - refresh also rejected                     → the session is genuinely over,
 *     so it is cleared and the UI returns to anonymous;
 *   - API unreachable / network failure         → the stored session is kept
 *     and revalidated later, so a momentarily offline API does not log the
 *     user out of the interface.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export const SESSION_KEY = "hydraclip.auth";

/** Subset of the API's UserPublic the UI needs. Extra fields are ignored. */
export type SessionUser = {
  id?: number;
  email: string;
  name?: string | null;
  role?: string;
  is_verified?: boolean;
};

/** Token pair as returned by /auth/login, /auth/supabase/* and /auth/refresh. */
export type TokenPair = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: SessionUser;
};

/** What is actually persisted: the pair plus the computed absolute expiry. */
export type StoredSession = {
  access_token: string;
  refresh_token: string;
  /** Epoch milliseconds, or null when unknown (legacy stored sessions). */
  expires_at: number | null;
  user: SessionUser;
};

export type AuthSession = {
  status: "anonymous" | "authenticated";
  user: SessionUser | null;
  /** True while the stored session is kept despite the API being unreachable. */
  offline: boolean;
  signOut: () => Promise<void>;
};

function storageAvailable(): boolean {
  return typeof localStorage !== "undefined";
}

/** Persist a fresh token pair, computing the absolute expiry timestamp. */
export function saveSession(tokens: TokenPair): StoredSession {
  const stored: StoredSession = {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
    expires_at:
      typeof tokens.expires_in === "number" && Number.isFinite(tokens.expires_in)
        ? Date.now() + tokens.expires_in * 1000
        : null,
    user: tokens.user,
  };
  if (storageAvailable()) {
    try {
      localStorage.setItem(SESSION_KEY, JSON.stringify(stored));
    } catch {
      // Quota/serialization failures must not break the login flow.
    }
  }
  return stored;
}

/**
 * Read the persisted session, or null when there is none.
 *
 * Sessions stored before expires_at was introduced only carry the relative
 * expires_in; their absolute expiry is unknowable, so they load with
 * expires_at: null and are validated against the API instead.
 */
export function loadStoredSession(): StoredSession | null {
  if (!storageAvailable()) return null;
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<StoredSession> & Partial<TokenPair>;
    if (typeof parsed.access_token !== "string" || parsed.access_token.length === 0) {
      return null;
    }
    if (typeof parsed.refresh_token !== "string" || parsed.refresh_token.length === 0) {
      return null;
    }
    if (!parsed.user || typeof parsed.user.email !== "string") {
      return null;
    }
    return {
      access_token: parsed.access_token,
      refresh_token: parsed.refresh_token,
      expires_at: typeof parsed.expires_at === "number" ? parsed.expires_at : null,
      user: parsed.user,
    };
  } catch {
    return null;
  }
}

export function clearSession(): void {
  if (!storageAvailable()) return;
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch {
    // Ignore — clearing is best-effort.
  }
}

/** Refresh slightly early so a token never expires mid-request. */
const EXPIRY_SKEW_MS = 15_000;
/** How long to wait before revalidating after a network/API failure. */
const RETRY_DELAY_MS = 45_000;

function isExpired(session: StoredSession): boolean {
  return session.expires_at !== null && session.expires_at - EXPIRY_SKEW_MS <= Date.now();
}

/** The API definitively rejected the credentials (401/403). */
class AuthInvalid extends Error {}
/** The API could not be reached or answered unexpectedly — try again later. */
class AuthUnavailable extends Error {}

async function requestMe(accessToken: string): Promise<SessionUser> {
  let response: Response;
  try {
    response = await fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${accessToken}` },
      credentials: "include",
    });
  } catch {
    throw new AuthUnavailable("The API is unreachable.");
  }
  if (response.status === 401 || response.status === 403) {
    throw new AuthInvalid("The access token was rejected.");
  }
  if (!response.ok) {
    throw new AuthUnavailable(`Unexpected /me response: ${response.status}.`);
  }
  return (await response.json()) as SessionUser;
}

async function requestRefresh(session: StoredSession): Promise<StoredSession> {
  let response: Response;
  try {
    response = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ refresh_token: session.refresh_token }),
    });
  } catch {
    throw new AuthUnavailable("The API is unreachable.");
  }
  if (response.status === 401 || response.status === 403) {
    throw new AuthInvalid("The refresh token was rejected.");
  }
  if (!response.ok) {
    throw new AuthUnavailable(`Unexpected /refresh response: ${response.status}.`);
  }
  const tokens = (await response.json()) as TokenPair;
  return saveSession(tokens);
}

const defaultSession: AuthSession = {
  status: "anonymous",
  user: null,
  offline: false,
  signOut: async () => {},
};

const AuthSessionContext = createContext<AuthSession>(defaultSession);

export function AuthSessionProvider({ children }: { children: ReactNode }) {
  // Read storage synchronously so the very first render already reflects the
  // persisted session — the header must never flash "Sign in" for a user who
  // is in fact signed in.
  const [state, setState] = useState<{
    session: StoredSession | null;
    offline: boolean;
  }>(() => ({ session: loadStoredSession(), offline: false }));

  useEffect(() => {
    if (typeof window === "undefined") return undefined;

    let cancelled = false;
    let retryTimer: number | undefined;

    async function validate(current: StoredSession) {
      try {
        let active = current;
        if (isExpired(active)) {
          active = await requestRefresh(active);
        }
        let user: SessionUser;
        try {
          user = await requestMe(active.access_token);
        } catch (error) {
          // Access token rejected despite a known expiry (clock skew, revoked
          // early): exchange the refresh token once before giving up.
          if (!(error instanceof AuthInvalid)) throw error;
          active = await requestRefresh(active);
          user = await requestMe(active.access_token);
        }
        const next: StoredSession = { ...active, user };
        try {
          localStorage.setItem(SESSION_KEY, JSON.stringify(next));
        } catch {
          // Non-fatal: the in-memory state below is authoritative.
        }
        if (!cancelled) setState({ session: next, offline: false });
      } catch (error) {
        if (cancelled) return;
        if (error instanceof AuthInvalid) {
          clearSession();
          setState({ session: null, offline: false });
          return;
        }
        // AuthUnavailable: keep the stored session and try again shortly, so
        // a stopped API container does not sign the user out of the UI.
        setState((prev) => (prev.session ? { ...prev, offline: true } : prev));
        retryTimer = window.setTimeout(() => {
          if (cancelled) return;
          const fresh = loadStoredSession();
          if (fresh) void validate(fresh);
        }, RETRY_DELAY_MS);
      }
    }

    const initial = loadStoredSession();
    if (initial) void validate(initial);

    const handleOnline = () => {
      const fresh = loadStoredSession();
      if (fresh) void validate(fresh);
    };
    const handleStorage = (event: StorageEvent) => {
      // Sign-in or sign-out in another tab mirrors into this one.
      if (event.key !== null && event.key !== SESSION_KEY) return;
      setState({ session: loadStoredSession(), offline: false });
    };
    window.addEventListener("online", handleOnline);
    window.addEventListener("storage", handleStorage);
    return () => {
      cancelled = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("storage", handleStorage);
    };
    // Validation runs once on mount; retries reschedule themselves.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const signOut = useCallback(async () => {
    const stored = loadStoredSession();
    clearSession();
    setState({ session: null, offline: false });
    if (stored) {
      try {
        await fetch("/api/auth/logout", {
          method: "POST",
          headers: { Authorization: `Bearer ${stored.access_token}` },
          credentials: "include",
        });
      } catch {
        // Best-effort: API tokens are stateless, the client discard is final.
      }
    }
  }, []);

  const value = useMemo<AuthSession>(
    () => ({
      status: state.session ? "authenticated" : "anonymous",
      user: state.session?.user ?? null,
      offline: state.offline,
      signOut,
    }),
    [state.session, state.offline, signOut],
  );

  return <AuthSessionContext.Provider value={value}>{children}</AuthSessionContext.Provider>;
}

export function useAuthSession(): AuthSession {
  return useContext(AuthSessionContext);
}
