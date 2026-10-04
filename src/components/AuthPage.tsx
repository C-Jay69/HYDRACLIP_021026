import { saveSession, useAuthSession, type TokenPair } from "@/auth-session";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ArrowLeft, CheckCircle2, Loader2 } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import brandMark from "../assets/hydraclip-mark.webp";

type AuthMode = "login" | "signup";

type AuthResult = {
  authenticated: boolean;
  requires_email_confirmation: boolean;
  message: string;
  tokens?: TokenPair | null;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    credentials: "include",
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Authentication request failed.");
  }
  return body as T;
}

export function AuthPage({ callback = false }: { callback?: boolean }) {
  const session = useAuthSession();
  const params = new URLSearchParams(window.location.search);
  const initialMode: AuthMode = params.get("mode") === "signup" ? "signup" : "login";
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(callback);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(params.get("error") ?? "");
  const [authenticated, setAuthenticated] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [providersLoaded, setProvidersLoaded] = useState(false);
  const [providerLoadFailed, setProviderLoadFailed] = useState(false);

  useEffect(() => {
    api<{ supabase_email: boolean; google: boolean }>("/api/auth/providers")
      .then((providers) => {
        setGoogleEnabled(providers.google);
        setEmailEnabled(providers.supabase_email);
      })
      .catch((reason: Error) => {
        setProviderLoadFailed(true);
        setError(reason.message);
      })
      .finally(() => setProvidersLoaded(true));
  }, []);

  useEffect(() => {
    if (!callback || params.get("provider") !== "google" || params.get("error")) {
      setBusy(false);
      return;
    }
    api<TokenPair>("/api/auth/google/exchange", { method: "POST", body: "{}" })
      .then((tokens) => {
        saveSession(tokens);
        setAuthenticated(true);
        setMessage(`Signed in as ${tokens.user.email}.`);
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setBusy(false));
    // The callback exchange must run exactly once when this route mounts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [callback]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await api<AuthResult>(`/api/auth/supabase/${mode}`, {
        method: "POST",
        body: JSON.stringify({ email, password, ...(mode === "signup" ? { name } : {}) }),
      });
      if (result.tokens) {
        saveSession(result.tokens);
        setAuthenticated(true);
      }
      setMessage(result.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Authentication failed.");
    } finally {
      setBusy(false);
    }
  }

  async function googleLogin() {
    setBusy(true);
    setError("");
    try {
      const result = await api<{ authorize_url: string }>("/api/auth/google/authorize");
      window.location.assign(result.authorize_url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Google login failed.");
      setBusy(false);
    }
  }

  // Signed in either just now (fresh tokens above) or from a restored
  // session — anyone reaching /auth already authenticated must never be
  // asked for credentials again.
  const signedIn = authenticated || session.status === "authenticated";

  function useDifferentAccount() {
    setAuthenticated(false);
    setMessage("");
    setError("");
    void session.signOut();
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-12">
      <section className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-2xl sm:p-8">
        <a href="/" className="mb-8 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> Back to HydraClip
        </a>
        <div className="mb-7 flex items-center gap-3">
          <img src={brandMark} alt="" className="size-11 rounded-xl" />
          <div>
            <p className="font-bold tracking-wide">HYDRACLIP</p>
            <p className="text-sm text-muted-foreground">Create and schedule videos</p>
          </div>
        </div>

        {busy && callback ? (
          <div className="flex items-center gap-3 rounded-lg border border-border bg-background p-4" role="status">
            <Loader2 className="size-5 animate-spin" /> Completing Google login…
          </div>
        ) : signedIn ? (
          <div className="space-y-5">
            <div className="flex items-start gap-3 rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-4">
              <CheckCircle2 className="mt-0.5 size-5 text-emerald-400" />
              <div>
                <p className="font-medium">You’re signed in</p>
                <p className="text-sm text-muted-foreground">
                  {message || `Signed in as ${session.user?.email ?? "your HydraClip account"}.`}
                </p>
              </div>
            </div>
            <Button className="w-full" asChild><a href="/">Continue to HydraClip</a></Button>
            <Button type="button" variant="ghost" className="w-full" onClick={useDifferentAccount}>
              Use a different account
            </Button>
          </div>
        ) : (
          <>
            <div className="mb-6 grid grid-cols-2 rounded-lg bg-secondary p-1">
              {(["login", "signup"] as const).map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => { setMode(item); setError(""); setMessage(""); }}
                  className={`rounded-md px-3 py-2 text-sm font-medium ${mode === item ? "bg-background shadow" : "text-muted-foreground"}`}
                >
                  {item === "login" ? "Sign in" : "Create account"}
                </button>
              ))}
            </div>

            {googleEnabled && (
              <Button type="button" variant="outline" className="mb-5 w-full" onClick={googleLogin} disabled={busy}>
                Continue with Google
              </Button>
            )}

            {googleEnabled && emailEnabled && <div className="mb-5 flex items-center gap-3 text-xs text-muted-foreground"><span className="h-px flex-1 bg-border" />or use email<span className="h-px flex-1 bg-border" /></div>}

            {!providersLoaded ? (
              <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />Loading login providers…</p>
            ) : providerLoadFailed ? null : emailEnabled ? (
              <form onSubmit={submit} className="space-y-4">
                {mode === "signup" && <div className="space-y-2"><Label htmlFor="auth-name">Name</Label><Input id="auth-name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></div>}
                <div className="space-y-2"><Label htmlFor="auth-email">Email</Label><Input id="auth-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></div>
                <div className="space-y-2"><Label htmlFor="auth-password">Password</Label><Input id="auth-password" type="password" required minLength={mode === "signup" ? 10 : 1} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "signup" ? "new-password" : "current-password"} /></div>
                <Button type="submit" className="w-full" disabled={busy}>{busy && <Loader2 className="size-4 animate-spin" />}{mode === "login" ? "Sign in" : "Create account"}</Button>
              </form>
            ) : (
              <p className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm">Email login is not configured on this deployment.</p>
            )}
          </>
        )}

        {message && !signedIn && <p className="mt-5 rounded-lg border border-brand/40 bg-brand/10 p-3 text-sm" role="status">{message}</p>}
        {error && <p className="mt-5 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive" role="alert">{error}</p>}
      </section>
    </main>
  );
}
