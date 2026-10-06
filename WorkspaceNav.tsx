/**
 * Navigation shell for every signed-in page.
 *
 * The landing header (SiteHeader) serves anonymous marketing traffic; this one
 * serves the app: primary destinations first, identity and sign-out last.
 * Pages render it under AuthSessionProvider so the session is available.
 */

import { useAuthSession } from "@/auth-session";
import { Button } from "@/components/ui/button";
import { CircleUserRound } from "lucide-react";

import brandMark from "../assets/hydraclip-mark.webp";

const APP_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/projects", label: "Projects" },
  { href: "/schedule", label: "Schedule" },
  { href: "/connect", label: "Accounts" },
  { href: "/billing", label: "Billing" },
  { href: "/profile", label: "Profile" },
] as const;

export function WorkspaceNav({ active }: { active: string }) {
  const session = useAuthSession();
  const label = session.user?.name || session.user?.email || "Account";
  const isAdmin = (session.user?.role ?? "USER").toUpperCase() === "ADMIN";
  const links = isAdmin ? [...APP_LINKS, { href: "/admin", label: "Admin" }] : APP_LINKS;

  return (
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
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              aria-current={link.href === active ? "page" : undefined}
              className={
                link.href === active
                  ? "rounded-md bg-secondary px-3 py-2 text-sm font-medium text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  : "rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              }
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <span
            className="hidden max-w-56 items-center gap-1.5 rounded-full border border-border bg-secondary/60 py-1.5 pr-3.5 pl-2.5 text-sm text-muted-foreground sm:inline-flex"
            title={session.user?.email ?? undefined}
          >
            <CircleUserRound className="size-4 shrink-0" aria-hidden="true" />
            <span className="truncate">{label}</span>
          </span>
          <Button
            variant="ghost"
            onClick={() => {
              void session.signOut();
              if (typeof window !== "undefined") window.location.assign("/");
            }}
          >
            Sign out
          </Button>
        </div>
      </div>

      {/* Mobile nav: same destinations, scrollable row. */}
      <nav
        aria-label="Workspace mobile"
        className="flex gap-1 overflow-x-auto border-t border-border px-4 py-2 md:hidden"
      >
        {links.map((link) => (
          <a
            key={link.href}
            href={link.href}
            aria-current={link.href === active ? "page" : undefined}
            className={
              link.href === active
                ? "shrink-0 rounded-md bg-secondary px-3 py-1.5 text-sm font-medium"
                : "shrink-0 rounded-md px-3 py-1.5 text-sm text-muted-foreground"
            }
          >
            {link.label}
          </a>
        ))}
      </nav>
    </header>
  );
}

/** Guard card for anonymous visitors; keeps expired sessions off the app. */
export function SignedOutGuard({ page }: { page: string }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6">
      <section className="w-full max-w-md rounded-2xl border border-border bg-card p-8 text-center shadow-2xl">
        <h1 className="text-xl font-bold">{page}</h1>
        <p className="mt-3 text-sm text-muted-foreground">
          You’re not signed in, or your session has expired. Sign in to continue.
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
