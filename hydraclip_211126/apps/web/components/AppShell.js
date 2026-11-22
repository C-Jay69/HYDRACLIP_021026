"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  CalendarClock,
  CreditCard,
  LayoutDashboard,
  LogOut,
  Menu,
  Send,
  Settings,
  Sparkles,
  Wand2,
  X,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const navigation = [
  { href: "/", label: "Studio", icon: LayoutDashboard },
  { href: "/billing", label: "Billing", icon: CreditCard },
  { href: "/schedules", label: "Schedules", icon: CalendarClock },
  { href: "/publishing", label: "Publishing", icon: Send },
  { href: "/settings", label: "Settings", icon: Settings },
];

function isActive(pathname, href) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-accent2 text-ink">
        <Sparkles className="h-5 w-5" />
      </span>
      <span>
        <span className="block text-sm font-bold leading-tight text-white">
          HydraClip
        </span>
        <span className="block text-[11px] font-medium uppercase tracking-wider text-muted">
          AI video studio
        </span>
      </span>
    </Link>
  );
}

export function AppShell({ children }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  const initials = (user?.name || user?.email || "U")
    .slice(0, 1)
    .toUpperCase();

  return (
    <div className="min-h-screen bg-hero">
      {open ? (
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm lg:hidden"
          aria-label="Close navigation"
        />
      ) : null}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-line/70 bg-panel/95 px-4 py-5 backdrop-blur transition-transform duration-200 lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-1">
          <Brand />
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="rounded-lg p-1.5 text-muted hover:bg-panel2 hover:text-white lg:hidden"
            aria-label="Close navigation"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <Link
          href="/#generate"
          className="btn btn-primary mt-6 w-full"
          onClick={() => setOpen(false)}
        >
          <Wand2 className="h-4 w-4" />
          Generate video
        </Link>

        <nav className="mt-6 flex flex-1 flex-col gap-1">
          {navigation.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 text-sm font-medium transition ${
                  active
                    ? "border-accent/20 bg-accent/10 text-accent"
                    : "border-transparent text-muted hover:border-line hover:bg-panel2/60 hover:text-white"
                }`}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="mt-4 rounded-xl border border-line bg-ink/50 p-3">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent2 to-accent text-sm font-bold text-ink">
              {initials}
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">
                {user?.name || "Creator"}
              </p>
              <p className="truncate text-xs text-muted">{user?.email}</p>
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between gap-2">
            <span className="badge border-accent/20 bg-accent/10 text-accent">
              {user?.plan || "Free"} plan
            </span>
            <button
              type="button"
              onClick={logout}
              className="rounded-lg p-1.5 text-muted transition hover:bg-red-500/10 hover:text-red-300"
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line/60 bg-ink/80 px-4 py-3 backdrop-blur lg:hidden">
          <Brand />
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="rounded-lg border border-line bg-panel2/60 p-2 text-slate-200"
            aria-label="Open navigation"
          >
            <Menu className="h-5 w-5" />
          </button>
        </header>

        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
          {children}
        </main>
      </div>
    </div>
  );
}
