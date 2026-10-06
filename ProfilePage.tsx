/**
 * Profile / account settings: edit display name, email and password.
 *
 * Mirrors PATCH /api/auth/me for profile updates and POST /api/auth/reset-password
 * for the password change. The page is intentionally minimal — the build prompt
 * lists /settings/profile as one page; this is it.
 */

import { SignedOutGuard, WorkspaceNav } from "@/components/WorkspaceNav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthSession } from "@/auth-session";
import { api } from "@/lib/api";
import { Loader2, UserCog } from "lucide-react";
import { useState } from "react";

export function ProfilePage() {
  const session = useAuthSession();
  const signedIn = session.status === "authenticated";

  const [name, setName] = useState(session.user?.name ?? "");
  const [email, setEmail] = useState(session.user?.email ?? "");
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  if (!signedIn) return <SignedOutGuard page="Profile" />;

  async function saveProfile(event: React.FormEvent) {
    event.preventDefault();
    setSavingProfile(true);
    setProfileError(null);
    setProfileMessage(null);
    try {
      const updated = await api<{ email: string; name?: string | null }>("/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ name, email }),
      });
      setProfileMessage("Profile updated.");
      // Reflect changes back into the auth session storage so other tabs pick it up.
      try {
        const raw = localStorage.getItem("hydraclip.auth");
        if (raw) {
          const parsed = JSON.parse(raw);
          parsed.user = { ...parsed.user, ...updated };
          localStorage.setItem("hydraclip.auth", JSON.stringify(parsed));
        }
      } catch {
        // Best-effort — the next /auth/me poll will pick up the new state.
      }
    } catch (caught) {
      setProfileError(caught instanceof Error ? caught.message : "Could not save.");
    } finally {
      setSavingProfile(false);
    }
  }

  async function savePassword(event: React.FormEvent) {
    event.preventDefault();
    if (newPassword.length < 10) {
      setPasswordError("New password must be at least 10 characters.");
      return;
    }
    setSavingPassword(true);
    setPasswordError(null);
    setPasswordMessage(null);
    try {
      // The backend reset endpoint accepts the old password as proof of identity
      // when called by an authenticated user — the seed admin / test user flow.
      const result = await api<{ message?: string }>("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({
          email,
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      setPasswordMessage(result.message ?? "Password changed.");
      setCurrentPassword("");
      setNewPassword("");
    } catch (caught) {
      setPasswordError(
        caught instanceof Error ? caught.message : "Could not change the password.",
      );
    } finally {
      setSavingPassword(false);
    }
  }

  return (
    <main className="min-h-screen bg-background">
      <WorkspaceNav active="/profile" />
      <div className="mx-auto max-w-3xl space-y-10 px-6 py-10">
        <section aria-labelledby="profile-heading">
          <div className="flex items-center gap-2.5">
            <UserCog className="size-5 text-brand-bright" aria-hidden="true" />
            <h1 id="profile-heading" className="text-2xl font-bold tracking-tight">
              Profile
            </h1>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Update your display name, email and password.
          </p>
        </section>

        <section aria-labelledby="profile-details">
          <h2 id="profile-details" className="text-lg font-bold">
            Account details
          </h2>
          <form
            onSubmit={(event) => void saveProfile(event)}
            className="mt-4 space-y-4 rounded-2xl border border-border bg-card p-5"
          >
            <div className="space-y-1.5">
              <Label htmlFor="profile-name">Display name</Label>
              <Input
                id="profile-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoComplete="name"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="profile-email">Email</Label>
              <Input
                id="profile-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                required
              />
            </div>
            <Button type="submit" disabled={savingProfile}>
              {savingProfile && <Loader2 className="size-4 animate-spin" />}
              Save profile
            </Button>
            {profileMessage && (
              <p role="status" className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-2.5 text-sm">
                {profileMessage}
              </p>
            )}
            {profileError && (
              <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 p-2.5 text-sm">
                {profileError}
              </p>
            )}
          </form>
        </section>

        <section aria-labelledby="profile-password">
          <h2 id="profile-password" className="text-lg font-bold">
            Change password
          </h2>
          <form
            onSubmit={(event) => void savePassword(event)}
            className="mt-4 space-y-4 rounded-2xl border border-border bg-card p-5"
          >
            <div className="space-y-1.5">
              <Label htmlFor="profile-current-password">Current password</Label>
              <Input
                id="profile-current-password"
                type="password"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                autoComplete="current-password"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="profile-new-password">New password</Label>
              <Input
                id="profile-new-password"
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                autoComplete="new-password"
                minLength={10}
                required
              />
              <p className="text-xs text-muted-foreground">At least 10 characters.</p>
            </div>
            <Button type="submit" disabled={savingPassword}>
              {savingPassword && <Loader2 className="size-4 animate-spin" />}
              Change password
            </Button>
            {passwordMessage && (
              <p role="status" className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-2.5 text-sm">
                {passwordMessage}
              </p>
            )}
            {passwordError && (
              <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 p-2.5 text-sm">
                {passwordError}
              </p>
            )}
          </form>
        </section>
      </div>
    </main>
  );
}
