/**
 * Signed-in home for HydraClip.
 *
 * Before this page existed every "Continue to HydraClip" action looped between
 * the landing page and /auth, because there was no app surface for an
 * authenticated user to actually land on. The dashboard is that destination:
 *
 *   - prominent action CTAs for the four flows the build prompt requires
 *     (create project, schedule a post, connect a social account, upgrade plan,
 *     open admin panel for admins),
 *   - a usage + connected-accounts summary so the user knows their state at a
 *     glance,
 *   - the existing projects list (kept), and
 *   - the stock media library as a working first tool.
 *
 * Anonymous visitors get a guard card instead of the app — the auth session is
 * restored synchronously from localStorage, so a stored (possibly expired)
 * session never flashes this state; it only appears once the session is known
 * to be gone.
 */
import { loadStoredSession, useAuthSession } from "@/auth-session";
import { Button } from "@/components/ui/button";
import { StockMediaBrowser } from "@/components/StockMediaBrowser";
import { api } from "@/lib/api";
import {
  CalendarClock,
  CircleUserRound,
  Clapperboard,
  CreditCard,
  FolderOpen,
  Link2,
  Loader2,
  PlayCircle,
  Plus,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";

import brandMark from "../assets/hydraclip-mark.webp";

type ProjectSummary = {
  id: number;
  title: string;
  status: string;
  video_count?: number;
  created_at?: string | null;
};

type ProjectsState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; items: ProjectSummary[] }
  | { status: "unavailable" };

type ConnectedAccount = {
  id: number;
  platform: string;
  account_name: string;
};

type BillingSummary = {
  plan_name?: string | null;
  status?: string | null;
  videos_used?: number;
  videos_limit?: number | null;
  storage_used_gb?: number;
  storage_limit_gb?: number | null;
};

function formatCreated(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toLocaleDateString();
}

export function DashboardPage() {
  const session = useAuthSession();
  const signedIn = session.status === "authenticated";
  const isAdmin = (session.user?.role ?? "USER").toUpperCase() === "ADMIN";
  const [projects, setProjects] = useState<ProjectsState>({ status: "idle" });
  const [accounts, setAccounts] = useState<ConnectedAccount[]>([]);
  const [billing, setBilling] = useState<BillingSummary | null>(null);

  useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;

    void (async () => {
      // Projects (existing flow — kept because it has its own loading state
      // surface in the UI).
      setProjects({ status: "loading" });
      try {
        const stored = loadStoredSession();
        const response = await fetch("/api/projects?limit=10", {
          headers: stored ? { Authorization: `Bearer ${stored.access_token}` } : {},
          credentials: "include",
        });
        if (cancelled) return;
        if (!response.ok) {
          setProjects({ status: "unavailable" });
        } else {
          const page = (await response.json()) as { items?: ProjectSummary[] };
          setProjects({
            status: "ready",
            items: Array.isArray(page.items) ? page.items : [],
          });
        }
      } catch {
        if (!cancelled) setProjects({ status: "unavailable" });
      }

      // Connected accounts + billing overview — best-effort, errors silently
      // fall back to empty so the dashboard is still usable in dev mode.
      try {
        setAccounts(await api<ConnectedAccount[]>("/social/accounts"));
      } catch {
        if (!cancelled) setAccounts([]);
      }
      try {
        const overview = await api<{
          subscription?: {
            plan_name?: string | null;
            status?: string | null;
          };
          plans?: Array<{ name: string; video_limit_monthly: number | null; storage_limit_gb: number | null }>;
        }>("/billing/overview");
        if (cancelled) return;
        const sub = overview.subscription ?? null;
        setBilling({
          plan_name: sub?.plan_name ?? null,
          status: sub?.status ?? null,
        });
      } catch {
        if (!cancelled) setBilling(null);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [signedIn]);

  function signOutAndLeave() {
    void session.signOut();
    if (typeof window !== "undefined") window.location.assign("/");
  }

  if (!signedIn) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-6">
        <section className="w-full max-w-md rounded-2xl border border-border bg-card p-8 text-center shadow-2xl">
          <h1 className="text-xl font-bold">Dashboard</h1>
          <p className="mt-3 text-sm text-muted-foreground">
            You’re not signed in, or your session has expired. Sign in to view your projects and
            media library.
          </p>
          <div className="mt-6 flex flex-col gap-2">
            <Button asChild>
              <a href="/auth">Go to sign in</a>
            </Button>
            <Button variant="ghost" asChild>
              <a href="/">Back to the landing page</a>
            </Button>
          </div>
        </section>
      </main>
    );
  }

  const displayName = session.user?.name || session.user?.email || "creator";

  return (
    <main className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 border-b border-border/80 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-3.5">
          <a
            href="/"
            aria-label="HydraClip landing page"
            className="flex items-center gap-2.5 rounded-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <img
              src={brandMark}
              alt=""
              aria-hidden="true"
              width={512}
              height={512}
              className="size-9 rounded-xl object-cover shadow-lg shadow-blue-500/15"
            />
            <span className="text-lg font-bold tracking-[0.04em]">
              HYDRA<span className="hc-gradient-text">CLIP</span>
            </span>
          </a>

          <nav aria-label="Workspace" className="hidden items-center gap-1 md:flex">
            <a href="/projects" className="rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground">
              Projects
            </a>
            <a href="/schedule" className="rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground">
              Schedule
            </a>
            <a href="/connect" className="rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground">
              Accounts
            </a>
            <a href="/billing" className="rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground">
              Billing
            </a>
            {isAdmin && (
              <a href="/admin" className="rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground">
                Admin
              </a>
            )}
          </nav>

          <div className="flex items-center gap-2">
            <span
              className="hidden max-w-56 items-center gap-1.5 rounded-full border border-border bg-secondary/60 py-1.5 pr-3.5 pl-2.5 text-sm text-muted-foreground sm:inline-flex"
              title={session.user?.email ?? undefined}
            >
              <CircleUserRound className="size-4 shrink-0" aria-hidden="true" />
              <span className="truncate">{displayName}</span>
            </span>
            <Button variant="ghost" onClick={signOutAndLeave}>
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl space-y-12 px-6 py-10 md:py-14">
        <section aria-labelledby="dashboard-welcome">
          <h1 id="dashboard-welcome" className="text-3xl font-extrabold tracking-tight">
            Welcome back, <span className="hc-gradient-text">{displayName}</span>
          </h1>
          <p className="mt-2 text-muted-foreground">
            This is your HydraClip workspace — projects, renders and media in one place.
          </p>
          {session.offline && (
            <p
              role="alert"
              className="mt-4 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm"
            >
              The HydraClip API is unreachable, so this page is showing your saved session. It
              keeps retrying in the background.
            </p>
          )}
        </section>

        {/* --- ACTION CARDS — the buttons the user was looking for --- */}
        <section aria-labelledby="dashboard-actions">
          <h2 id="dashboard-actions" className="sr-only">
            Quick actions
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <ActionCard
              href="/projects"
              icon={<Plus className="size-5" aria-hidden="true" />}
              title="Create a project"
              description="Enter a topic, generate a script, voiceover and rendered video."
            />
            <ActionCard
              href="/schedule"
              icon={<CalendarClock className="size-5" aria-hidden="true" />}
              title="Schedule a post"
              description="Queue a finished video to publish to YouTube, Instagram, TikTok or X."
            />
            <ActionCard
              href="/connect"
              icon={<Link2 className="size-5" aria-hidden="true" />}
              title="Connect a platform"
              description={
                accounts.length === 0
                  ? "Link your YouTube account to enable auto-publish."
                  : `${accounts.length} account${accounts.length === 1 ? "" : "s"} connected.`
              }
            />
            <ActionCard
              href="/billing"
              icon={<CreditCard className="size-5" aria-hidden="true" />}
              title={
                billing?.plan_name
                  ? `${billing.plan_name} plan`
                  : "Upgrade your plan"
              }
              description={
                billing?.status
                  ? `Subscription ${billing.status}. Manage in Stripe.`
                  : "Unlock more videos, remove the watermark, enable auto-publish."
              }
            />
          </div>

          {isAdmin && (
            <div className="mt-4">
              <Button variant="outline" asChild>
                <a href="/admin">
                  <ShieldCheck className="size-4" aria-hidden="true" />
                  Open admin panel
                </a>
              </Button>
            </div>
          )}
        </section>

        {/* --- STATUS GRID — usage + connected accounts --- */}
        <section aria-labelledby="dashboard-status">
          <h2 id="dashboard-status" className="text-xl font-bold tracking-tight">
            Status
          </h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <StatusCard
              label="Plan"
              value={billing?.plan_name ?? "Free"}
              sub={billing?.status ? `Subscription ${billing.status}` : "Default tier"}
            />
            <StatusCard
              label="Connected platforms"
              value={String(accounts.length)}
              sub={
                accounts.length === 0
                  ? "None yet — connect one to publish"
                  : accounts.map((a) => a.platform).join(", ")
              }
            />
            <StatusCard
              label="Account"
              value={session.user?.email ?? "—"}
              sub={`Role: ${(session.user?.role ?? "USER").toUpperCase()}`}
            />
          </div>
        </section>

        {/* --- RECENT PROJECTS --- */}
        <section aria-labelledby="dashboard-projects">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <FolderOpen className="size-5 text-brand-bright" aria-hidden="true" />
              <h2 id="dashboard-projects" className="text-xl font-bold tracking-tight">
                Your projects
              </h2>
            </div>
            <Button asChild size="sm">
              <a href="/projects">
                <PlayCircle className="size-4" />
                Open projects
              </a>
            </Button>
          </div>

          {projects.status === "loading" ? (
            <p className="mt-4 flex items-center gap-2 text-sm text-muted-foreground" role="status">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Loading projects…
            </p>
          ) : projects.status === "unavailable" ? (
            <p className="mt-4 rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
              Projects load from the HydraClip API. Start the backend containers and refresh this
              page to see them.
            </p>
          ) : projects.status === "ready" && projects.items.length > 0 ? (
            <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {projects.items.map((project) => {
                const created = formatCreated(project.created_at);
                return (
                  <li key={project.id}>
                    <a
                      href="/projects"
                      className="block rounded-xl border border-border bg-card p-4 shadow-sm transition-colors hover:border-ring/60"
                    >
                      <p className="truncate font-medium">{project.title}</p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {project.status}
                        {typeof project.video_count === "number" && ` · ${project.video_count} videos`}
                        {created && ` · ${created}`}
                      </p>
                    </a>
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="mt-4 rounded-lg border border-dashed border-border bg-card/60 p-6 text-sm text-muted-foreground">
              <p className="flex items-center gap-2">
                <Sparkles className="size-4 text-brand-bright" aria-hidden="true" />
                No projects yet.
              </p>
              <p className="mt-1">
                <a href="/projects" className="font-medium text-foreground underline">
                  Create your first project
                </a>{" "}
                — enter a topic and HydraClip will draft a script, voiceover and rendered video.
              </p>
            </div>
          )}
        </section>

        {/* --- QUICK START CARD --- */}
        <section aria-labelledby="dashboard-quick">
          <div className="rounded-2xl border border-border bg-card p-5">
            <div className="flex items-center gap-2.5">
              <Clapperboard className="size-5 text-brand-bright" aria-hidden="true" />
              <h2 id="dashboard-quick" className="text-lg font-bold">
                How it works
              </h2>
            </div>
            <ol className="mt-4 grid gap-3 sm:grid-cols-3">
              <li className="rounded-xl border border-border bg-background p-4 text-sm">
                <p className="font-medium">1. Create a project</p>
                <p className="mt-1 text-muted-foreground">
                  Pick a topic and a tone — HydraClip drafts a script and scene plan with local AI.
                </p>
                <Button asChild variant="link" size="sm" className="mt-2 px-0">
                  <a href="/projects">Open Projects →</a>
                </Button>
              </li>
              <li className="rounded-xl border border-border bg-background p-4 text-sm">
                <p className="font-medium">2. Generate &amp; preview</p>
                <p className="mt-1 text-muted-foreground">
                  Generate voiceover, captions and the rendered video. Re-run any stage you don’t like.
                </p>
              </li>
              <li className="rounded-xl border border-border bg-background p-4 text-sm">
                <p className="font-medium">3. Schedule or publish</p>
                <p className="mt-1 text-muted-foreground">
                  Queue it for YouTube auto-publish, or download the bundle for TikTok / Instagram / X.
                </p>
                <Button asChild variant="link" size="sm" className="mt-2 px-0">
                  <a href="/schedule">Open Schedule →</a>
                </Button>
              </li>
            </ol>
          </div>
        </section>

        {/* --- STOCK MEDIA LIBRARY (kept) --- */}
        <section aria-labelledby="dashboard-media-heading" id="dashboard-media">
          <div className="flex items-center gap-2.5">
            <Clapperboard className="size-5 text-brand-bright" aria-hidden="true" />
            <h2 id="dashboard-media-heading" className="text-xl font-bold tracking-tight">
              Stock media library
            </h2>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Search licensed footage and images for your next video.
          </p>
          <div className="mt-5 rounded-2xl border border-border bg-card p-4 sm:p-6">
            <StockMediaBrowser />
          </div>
        </section>
      </div>
    </main>
  );
}

/** Big square action card used in the quick-actions row at the top. */
function ActionCard({
  href,
  icon,
  title,
  description,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <a
      href={href}
      className="group flex flex-col gap-3 rounded-2xl border border-border bg-card p-5 shadow-sm transition-all hover:border-ring/60 hover:shadow-md"
    >
      <span className="inline-flex size-10 items-center justify-center rounded-xl bg-brand/10 text-brand-bright">
        {icon}
      </span>
      <p className="font-bold tracking-tight">{title}</p>
      <p className="text-sm text-muted-foreground">{description}</p>
    </a>
  );
}

/** Small label + value card used in the status row. */
function StatusCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 truncate text-lg font-bold tracking-tight">{value}</p>
      {sub && <p className="mt-1 truncate text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}
