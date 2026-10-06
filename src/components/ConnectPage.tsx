/**
 * Connected social accounts.
 *
 * The build prompt requires a "/connect" page where users link YouTube,
 * Instagram, TikTok and X. This page lists the four supported platforms,
 * shows what's already connected, starts the OAuth flow via
 * /api/oauth/{platform}/authorize, and lets users disconnect.
 *
 * The backend honestly reports which platforms are auto-publishable and
 * which require a manual fallback — this UI surfaces that information so
 * users aren't surprised when TikTok "publishes" as a download bundle.
 */

import { SignedOutGuard, WorkspaceNav } from "@/components/WorkspaceNav";
import { Button } from "@/components/ui/button";
import { useAuthSession } from "@/auth-session";
import { api } from "@/lib/api";
import {
  CheckCircle2,
  Link2,
  Loader2,
  PlugZap,
  Unplug,
} from "lucide-react";
import { useEffect, useState } from "react";

type PlatformInfo = {
  name: string;
  label: string;
  configured: boolean;
  requires_public_url: boolean;
  detail: string | null;
};

type ConnectedAccount = {
  id: number;
  platform: string;
  account_name: string;
  account_id: string | null;
  is_active: boolean;
};

const PLATFORM_NOTES: Record<string, string> = {
  youtube: "Auto-publish via YouTube Data API v3. Requires Google OAuth credentials.",
  instagram:
    "Official Content Publishing API needs a business account and approved partners — this UI ships the connector and a manual export fallback.",
  tiktok:
    "TikTok Research API does not allow direct upload — connector is wired, publish path falls back to a prefilled metadata download.",
  x:
    "X Media Upload + Tweet API works for paid API tier — connector is wired, manual fallback otherwise.",
};

export function ConnectPage() {
  const session = useAuthSession();
  const signedIn = session.status === "authenticated";

  const [platforms, setPlatforms] = useState<PlatformInfo[] | null>(null);
  const [accounts, setAccounts] = useState<ConnectedAccount[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!signedIn) return;
    void (async () => {
      try {
        const [platformList, accountList] = await Promise.all([
          api<PlatformInfo[]>("/oauth/platforms"),
          api<ConnectedAccount[]>("/social/accounts"),
        ]);
        setPlatforms(platformList);
        setAccounts(accountList);
      } catch (caught) {
        setError(
          caught instanceof Error ? caught.message : "Could not load social platforms.",
        );
      }
    })();
  }, [signedIn]);

  // If the OAuth callback redirected back here with a status query param,
  // surface it so the user knows whether the connection succeeded.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const status = params.get("status");
    const platform = params.get("platform");
    const detail = params.get("detail");
    if (status && platform) {
      if (status === "connected") {
        setMessage(`Connected ${platform}${detail ? ` as ${detail}` : ""}.`);
      } else {
        setError(`Could not connect ${platform}: ${detail ?? "unknown error"}.`);
      }
      // Clean the URL so the message doesn't persist on refresh.
      window.history.replaceState({}, "", "/connect");
    }
  }, []);

  if (!signedIn) return <SignedOutGuard page="Connect" />;

  async function connect(platform: string) {
    setBusy(platform);
    setError(null);
    setMessage(null);
    try {
      const result = await api<{ authorize_url: string }>(
        `/oauth/${platform}/authorize`,
      );
      window.location.assign(result.authorize_url);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : `Could not start ${platform} OAuth.`,
      );
      setBusy(null);
    }
  }

  async function disconnect(account: ConnectedAccount) {
    setBusy(`${account.platform}:${account.id}`);
    setError(null);
    try {
      await api(`/social/accounts/${account.id}`, { method: "DELETE" });
      setAccounts((current) =>
        current.filter((row) => row.id !== account.id),
      );
      setMessage(`Disconnected ${account.platform}.`);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not disconnect the account.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="min-h-screen bg-background">
      <WorkspaceNav active="/connect" />
      <div className="mx-auto max-w-7xl space-y-10 px-6 py-10">
        <section aria-labelledby="connect-heading">
          <div className="flex items-center gap-2.5">
            <PlugZap className="size-5 text-brand-bright" aria-hidden="true" />
            <h1 id="connect-heading" className="text-2xl font-bold tracking-tight">
              Connected accounts
            </h1>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Link the platforms you want to publish to. Only YouTube supports full
            auto-publish with standard OAuth — the others fall back to a compliant
            manual export workflow.
          </p>

          {message && (
            <p
              role="status"
              className="mt-4 rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm"
            >
              {message}
            </p>
          )}
          {error && (
            <p
              role="alert"
              className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm"
            >
              {error}
            </p>
          )}
        </section>

        <section aria-labelledby="connect-platforms">
          <h2 id="connect-platforms" className="sr-only">
            Available platforms
          </h2>

          {!platforms ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              Loading platforms…
            </p>
          ) : (
            <ul className="grid gap-3 md:grid-cols-2">
              {platforms.map((platform) => {
                const connected = accounts.filter(
                  (row) => row.platform === platform.name,
                );
                return (
                  <li
                    key={platform.name}
                    className="rounded-2xl border border-border bg-card p-5"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-lg font-bold">{platform.label}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {PLATFORM_NOTES[platform.name] ?? "Connector available."}
                        </p>
                      </div>
                      {connected.length > 0 && (
                        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-500">
                          <CheckCircle2 className="size-3" aria-hidden="true" />
                          {connected.length} linked
                        </span>
                      )}
                    </div>

                    {!platform.configured && (
                      <p className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-2.5 text-xs">
                        Backend not configured
                        {platform.detail ? `: ${platform.detail}` : "."}
                      </p>
                    )}

                    {connected.length > 0 ? (
                      <ul className="mt-3 space-y-2">
                        {connected.map((account) => (
                          <li
                            key={account.id}
                            className="flex items-center justify-between gap-2 rounded-lg border border-border bg-background p-2.5 text-sm"
                          >
                            <span className="flex items-center gap-2 truncate">
                              <Link2 className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                              <span className="truncate">{account.account_name || `Account #${account.id}`}</span>
                            </span>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={busy === `${account.platform}:${account.id}`}
                              onClick={() => void disconnect(account)}
                            >
                              <Unplug className="size-4" />
                              Disconnect
                            </Button>
                          </li>
                        ))}
                      </ul>
                    ) : null}

                    <div className="mt-4">
                      <Button
                        disabled={!platform.configured || busy === platform.name}
                        onClick={() => void connect(platform.name)}
                        className="w-full sm:w-auto"
                      >
                        {busy === platform.name ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <Link2 className="size-4" />
                        )}
                        {connected.length > 0 ? "Connect another" : `Connect ${platform.label}`}
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
