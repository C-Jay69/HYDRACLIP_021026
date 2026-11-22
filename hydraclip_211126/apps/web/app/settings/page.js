"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Gauge,
  Link2,
  Loader2,
  LogOut,
  Save,
  Shield,
  Unlink,
  User,
} from "lucide-react";
import { api, getApiBase } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/Toast";
import { formatDate, formatLimit, platformLabel } from "@/lib/format";

export default function SettingsPage() {
  const { user, refreshUser, logout } = useAuth();
  const { push } = useToast();

  const [name, setName] = useState(user?.name || "");
  const [email, setEmail] = useState(user?.email || "");
  const [saving, setSaving] = useState(false);
  const [usage, setUsage] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busyPlatform, setBusyPlatform] = useState("");

  useEffect(() => {
    setName(user?.name || "");
    setEmail(user?.email || "");
  }, [user]);

  const load = useCallback(async () => {
    try {
      const [usageData, accountList, healthData] = await Promise.all([
        api.usage(),
        api.socialAccounts(),
        api.health().catch(() => null),
      ]);
      setUsage(usageData);
      setAccounts(accountList);
      setHealth(healthData);
    } catch (err) {
      push(err?.message || "Could not load settings.", "error");
    } finally {
      setLoading(false);
    }
  }, [push]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSaveProfile(event) {
    event.preventDefault();
    if (!name.trim() || !email.trim()) {
      push("Name and email are required.", "warning");
      return;
    }
    setSaving(true);
    try {
      await api.updateProfile({ name: name.trim(), email: email.trim() });
      await refreshUser();
      push("Profile updated.", "success");
    } catch (err) {
      push(err?.message || "Could not update your profile.", "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleConnectYouTube() {
    setBusyPlatform("youtube");
    try {
      const result = await api.youtubeConnect();
      if (result?.auth_url) {
        window.open(result.auth_url, "_blank", "noopener,noreferrer");
        push("YouTube authorization opened in a new tab.", "info");
      } else {
        push("YouTube OAuth is not configured.", "warning");
      }
    } catch (err) {
      push(err?.message || "Could not start YouTube OAuth.", "error");
    } finally {
      setBusyPlatform("");
    }
  }

  async function handleDisconnect(account) {
    if (
      !window.confirm(
        `Disconnect ${platformLabel(account.platform)} (${account.account_name})?`,
      )
    ) {
      return;
    }
    setBusyPlatform(account.platform);
    try {
      await api.disconnectSocial(account.platform);
      setAccounts((current) =>
        current.filter((item) => item.id !== account.id),
      );
      push("Account disconnected.", "success");
    } catch (err) {
      push(err?.message || "Could not disconnect the account.", "error");
    } finally {
      setBusyPlatform("");
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">
          Settings
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-white">
          Your account
        </h1>
        <p className="mt-1 text-sm text-muted">
          Manage your profile, connected platforms and usage.
        </p>
      </header>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          <section className="card p-5">
            <div className="flex items-center gap-3">
              <span className="rounded-xl border border-line bg-panel2/70 p-2 text-accent">
                <User className="h-5 w-5" />
              </span>
              <div>
                <h2 className="text-sm font-semibold text-white">Profile</h2>
                <p className="text-xs text-muted">
                  This is the name shown in your studio.
                </p>
              </div>
            </div>

            <form onSubmit={handleSaveProfile} className="mt-4 space-y-4">
              <div>
                <label className="label" htmlFor="settings-name">
                  Name
                </label>
                <input
                  id="settings-name"
                  className="input"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </div>
              <div>
                <label className="label" htmlFor="settings-email">
                  Email
                </label>
                <input
                  id="settings-email"
                  type="email"
                  className="input"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </div>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={saving}
              >
                {saving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                {saving ? "Saving…" : "Save profile"}
              </button>
            </form>
          </section>

          <section className="card p-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="rounded-xl border border-line bg-panel2/70 p-2 text-accent2">
                  <Link2 className="h-5 w-5" />
                </span>
                <div>
                  <h2 className="text-sm font-semibold text-white">
                    Connected platforms
                  </h2>
                  <p className="text-xs text-muted">
                    Used when publishing scheduled videos.
                  </p>
                </div>
              </div>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={handleConnectYouTube}
                disabled={busyPlatform === "youtube"}
              >
                {busyPlatform === "youtube" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Link2 className="h-3.5 w-3.5" />
                )}
                Connect YouTube
              </button>
            </div>

            <div className="mt-4">
              {accounts.length === 0 ? (
                <div className="rounded-xl border border-dashed border-line p-6 text-center text-sm text-muted">
                  No platforms connected yet.
                </div>
              ) : (
                <ul className="space-y-2">
                  {accounts.map((account) => (
                    <li
                      key={account.id}
                      className="flex items-center justify-between gap-3 rounded-xl border border-line bg-ink/40 p-3"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-white">
                          {platformLabel(account.platform)}
                        </p>
                        <p className="truncate text-xs text-muted">
                          {account.account_name} · connected{" "}
                          {formatDate(account.connected_at)}
                        </p>
                      </div>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDisconnect(account)}
                        disabled={busyPlatform === account.platform}
                      >
                        {busyPlatform === account.platform ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Unlink className="h-3.5 w-3.5" />
                        )}
                        Disconnect
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <p className="mt-3 flex items-start gap-1.5 text-xs text-muted">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              YouTube OAuth needs `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` and
              a matching redirect URI in your `.env`.
            </p>
          </section>
        </div>

        <aside className="space-y-5">
          <section className="card p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">Usage</h2>
              <Gauge className="h-4 w-4 text-accent" />
            </div>
            {loading ? (
              <div className="mt-4 flex items-center gap-2 text-xs text-muted">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Loading…
              </div>
            ) : (
              <dl className="mt-4 space-y-2.5 text-xs">
                <div className="flex items-center justify-between">
                  <dt className="text-muted">Videos this month</dt>
                  <dd className="font-mono text-slate-200">
                    {usage
                      ? `${usage.videos_this_month} / ${formatLimit(
                          usage.video_limit_monthly,
                        )}`
                      : "—"}
                  </dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-muted">Storage</dt>
                  <dd className="font-mono text-slate-200">
                    {usage
                      ? `${usage.storage_used_gb} / ${usage.storage_limit_gb} GB`
                      : "—"}
                  </dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-muted">Plan</dt>
                  <dd className="font-semibold text-accent">
                    {user?.plan || "Free"}
                  </dd>
                </div>
              </dl>
            )}
            <Link href="/billing" className="btn btn-ghost btn-sm mt-4 w-full">
              Manage plan
            </Link>
          </section>

          <section className="card p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">API</h2>
              <Shield className="h-4 w-4 text-accent2" />
            </div>
            <p className="mt-3 break-all text-xs text-muted">{getApiBase()}</p>
            <p className="mt-2 inline-flex items-center gap-1.5 text-xs">
              {health?.status === "ready" ? (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />
                  <span className="text-emerald-300">Connected</span>
                </>
              ) : (
                <>
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-300" />
                  <span className="text-amber-300">Not reachable</span>
                </>
              )}
            </p>
            {health?.database ? (
              <p className="mt-1 text-xs text-muted">
                Database: {health.database}
              </p>
            ) : null}
          </section>

          <section className="card p-5">
            <h2 className="text-sm font-semibold text-white">Session</h2>
            <p className="mt-1 text-xs text-muted">
              Signing out clears the tokens stored in this browser.
            </p>
            <button
              type="button"
              className="btn btn-danger mt-3 w-full"
              onClick={logout}
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </section>
        </aside>
      </div>
    </div>
  );
}
