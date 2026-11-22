"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { AuthPanel } from "./AuthPanel";
import { AppShell } from "./AppShell";

export function AuthGate({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-hero text-muted">
        <div className="flex items-center gap-2 text-xl font-bold text-white">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-accent2 text-ink">
            <Sparkles className="h-5 w-5" />
          </span>
          HydraClip
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Loader2 className="h-4 w-4 animate-spin" />
          Connecting to your studio…
        </div>
      </div>
    );
  }

  if (!user) return <AuthPanel />;

  return <AppShell>{children}</AppShell>;
}
