/**
 * Admin dashboard: top-line platform metrics + recent audit log entries.
 *
 * Backed by /api/admin/stats (counts of users, projects, videos, subscriptions)
 * and /api/admin/audit-logs. The backend enforces ADMIN role on every /admin/*
 * endpoint, so non-admins get a clear 403 message instead of a blank page.
 */

import { SignedOutGuard, WorkspaceNav } from "@/components/WorkspaceNav";
import { Button } from "@/components/ui/button";
import { useAuthSession } from "@/auth-session";
import { api } from "@/lib/api";
import { BarChart3, Loader2, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";

type AdminStats = {
  users: number;
  active_users: number;
  projects: number;
  videos: number;
  completed_videos: number;
  failed_videos: number;
  active_subscriptions: number;
  plan_breakdown: Record<string, number>;
};

type AuditLog = {
  id: number;
  admin_id: number;
  action: string;
  target_type: string | null;
  target_id: number | null;
  metadata_json: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
};

export function AdminPage() {
  const session = useAuthSession();
  const signedIn = session.status === "authenticated";
  const isAdmin = (session.user?.role ?? "USER").toUpperCase() === "ADMIN";

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!signedIn || !isAdmin) {
      setLoading(false);
      return;
    }
    void (async () => {
      try {
        const [statsData, logPage] = await Promise.all([
          api<AdminStats>("/admin/stats"),
          api<{ items?: AuditLog[] }>("/admin/audit-logs?limit=20"),
        ]);
        setStats(statsData);
        setLogs(Array.isArray(logPage.items) ? logPage.items : []);
      } catch (caught) {
        setError(
          caught instanceof Error ? caught.message : "Could not load admin data.",
        );
      } finally {
        setLoading(false);
      }
    })();
  }, [signedIn, isAdmin]);

  if (!signedIn) return <SignedOutGuard page="Admin" />;

  if (!isAdmin) {
    return (
      <main className="min-h-screen bg-background">
        <WorkspaceNav active="/admin" />
        <div className="mx-auto max-w-3xl px-6 py-16">
          <div className="rounded-2xl border border-amber-500/40 bg-amber-500/10 p-6 text-center">
            <ShieldAlert className="mx-auto size-10 text-amber-500" aria-hidden="true" />
            <h1 className="mt-4 text-xl font-bold">Admin access required</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Your account ({session.user?.email ?? "anonymous"}) does not have the ADMIN role.
              Sign in with the seeded admin credentials from <code className="font-mono">ADMIN_EMAIL</code> /
              <code className="font-mono"> ADMIN_PASSWORD</code> to use this page.
            </p>
            <Button asChild className="mt-5">
              <a href="/dashboard">Back to dashboard</a>
            </Button>
          </div>
        </div>
      </main>
    );
  }

  const statsCards: Array<{ label: string; value: number | string; sub?: string }> = stats
    ? [
        { label: "Total users", value: stats.users, sub: `${stats.active_users} active` },
        { label: "Active subscriptions", value: stats.active_subscriptions },
        { label: "Projects", value: stats.projects },
        { label: "Videos generated", value: stats.videos, sub: `${stats.completed_videos} done · ${stats.failed_videos} failed` },
      ]
    : [];

  return (
    <main className="min-h-screen bg-background">
      <WorkspaceNav active="/admin" />
      <div className="mx-auto max-w-7xl space-y-10 px-6 py-10">
        <section aria-labelledby="admin-heading">
          <div className="flex items-center gap-2.5">
            <BarChart3 className="size-5 text-brand-bright" aria-hidden="true" />
            <h1 id="admin-heading" className="text-2xl font-bold tracking-tight">
              Admin overview
            </h1>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Platform metrics and recent admin actions. The full management tables
            (users, jobs, settings, logs) live under <code className="font-mono">/admin/users</code>,
            <code className="font-mono"> /admin/jobs</code>, etc. — this page is the dashboard.
          </p>
        </section>

        {error && (
          <p
            role="alert"
            className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm"
          >
            {error}
          </p>
        )}

        {loading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            Loading admin metrics…
          </p>
        ) : (
          <section aria-labelledby="admin-stats">
            <h2 id="admin-stats" className="sr-only">
              Platform metrics
            </h2>
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {statsCards.map((card) => (
                <li key={card.label} className="rounded-2xl border border-border bg-card p-5">
                  <p className="text-sm text-muted-foreground">{card.label}</p>
                  <p className="mt-2 text-3xl font-bold tracking-tight">{card.value}</p>
                  {card.sub && (
                    <p className="mt-1 text-xs text-muted-foreground">{card.sub}</p>
                  )}
                </li>
              ))}
            </ul>

            {stats && Object.keys(stats.plan_breakdown).length > 0 && (
              <div className="mt-6 rounded-2xl border border-border bg-card p-5">
                <p className="text-sm font-semibold">Active subscriptions by plan</p>
                <ul className="mt-3 space-y-2">
                  {Object.entries(stats.plan_breakdown).map(([plan, count]) => (
                    <li
                      key={plan}
                      className="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2 text-sm"
                    >
                      <span className="font-medium">{plan}</span>
                      <span className="text-muted-foreground">{count} active</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}

        <section aria-labelledby="admin-logs">
          <h2 id="admin-logs" className="text-lg font-bold">
            Recent admin actions
          </h2>
          {logs.length === 0 ? (
            <p className="mt-3 rounded-lg border border-dashed border-border bg-card/60 p-6 text-sm text-muted-foreground">
              No admin actions logged yet.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {logs.map((log) => (
                <li
                  key={log.id}
                  className="rounded-xl border border-border bg-card p-4 text-sm"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium">{log.action}</p>
                    <time className="text-xs text-muted-foreground">
                      {new Date(log.created_at).toLocaleString()}
                    </time>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    by admin #{log.admin_id}
                    {log.target_type ? ` · target ${log.target_type} #${log.target_id}` : ""}
                    {log.ip_address ? ` · ${log.ip_address}` : ""}
                  </p>
                  {log.metadata_json && Object.keys(log.metadata_json).length > 0 && (
                    <pre className="mt-2 overflow-x-auto rounded bg-background p-2 text-xs">
                      {JSON.stringify(log.metadata_json, null, 2)}
                    </pre>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
