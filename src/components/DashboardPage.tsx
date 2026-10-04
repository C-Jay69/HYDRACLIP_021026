/**
 * Signed-in home for HydraClip.
 *
 * Before this page existed every "Continue to HydraClip" action looped between
 * the landing page and /auth, because there was no app surface for an
 * authenticated user to actually land on. The dashboard is that destination:
 * account identity, projects fetched from the API (when it is reachable), and
 * the stock media library as a working first tool.
 *
 * Anonymous visitors get a guard card instead of the app — the auth session is
 * restored synchronously from localStorage, so a stored (possibly expired)
 * session never flashes this state; it only appears once the session is known
 * to be gone.
 */
import { loadStoredSession, useAuthSession } from "@/auth-session";
import { StockMediaBrowser } from "@/components/StockMediaBrowser";
import { Button } from "@/components/ui/button";
import { CircleUserRound, Clapperboard, FolderOpen, Loader2 } from "lucide-react";
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

function formatCreated(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toLocaleDateString();
}

export function DashboardPage() {
  const session = useAuthSession();
  const signedIn = session.status === "authenticated";
  const [projects, setProjects] = useState<ProjectsState>({ status: "idle" });

  useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;
    setProjects({ status: "loading" });

    void (async () => {
      try {
        const stored = loadStoredSession();
        const response = await fetch("/api/projects", {
          headers: stored ? { Authorization: `Bearer ${stored.access_token}` } : {},
          credentials: "include",
        });
        if (cancelled) return;
        if (!response.ok) {
          setProjects({ status: "unavailable" });
          return;
        }
        const page = (await response.json()) as { items?: ProjectSummary[] };
        setProjects({ status: "ready", items: Array.isArray(page.items) ? page.items : [] });
      } catch {
        if (!cancelled) setProjects({ status: "unavailable" });
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

        <section aria-labelledby="dashboard-projects">
          <div className="flex items-center gap-2.5">
            <FolderOpen className="size-5 text-brand-bright" aria-hidden="true" />
            <h2 id="dashboard-projects" className="text-xl font-bold tracking-tight">
              Your projects
            </h2>
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
                  <li
                    key={project.id}
                    className="rounded-xl border border-border bg-card p-4 shadow-sm"
                  >
                    <p className="truncate font-medium">{project.title}</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {project.status}
                      {typeof project.video_count === "number" && ` · ${project.video_count} videos`}
                      {created && ` · ${created}`}
                    </p>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="mt-4 rounded-lg border border-dashed border-border bg-card/60 p-6 text-sm text-muted-foreground">
              No projects yet. Once the generation UI ships, videos you create will show up
              here — meanwhile, the media library below is fully usable.
            </p>
          )}
        </section>

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
