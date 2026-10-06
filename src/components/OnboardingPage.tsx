/**
 * First-run onboarding wizard.
 *
 * Build prompt section "User onboarding wizard": walk a brand-new signed-in
 * user through 3 quick steps (welcome, what to create, connect a platform)
 * and dump them at /projects. Existing users can skip it via the nav.
 */

import { SignedOutGuard, WorkspaceNav } from "@/components/WorkspaceNav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthSession } from "@/auth-session";
import { api } from "@/lib/api";
import {
  ArrowRight,
  CheckCircle2,
  Clapperboard,
  Sparkles,
  Wand2,
} from "lucide-react";
import { useState } from "react";

export function OnboardingPage() {
  const session = useAuthSession();
  const signedIn = session.status === "authenticated";
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [name, setName] = useState(session.user?.name ?? "");
  const [firstTopic, setFirstTopic] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!signedIn) return <SignedOutGuard page="Onboarding" />;

  async function saveNameAndCreate() {
    if (!firstTopic.trim()) {
      setStep(3);
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const created = await api<{ id: number }>("/projects", {
        method: "POST",
        body: JSON.stringify({
          title: firstTopic.trim(),
          topic: null,
        }),
      });
      // Save the name in parallel — non-blocking, errors ignored.
      if (name && name !== session.user?.name) {
        void api("/auth/me", {
          method: "PATCH",
          body: JSON.stringify({ name }),
        });
      }
      window.location.assign(`/projects`);
      void created;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create the project.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <main className="min-h-screen bg-background">
      <WorkspaceNav active="/dashboard" />
      <div className="mx-auto max-w-2xl px-6 py-12">
        <div className="rounded-2xl border border-border bg-card p-6 shadow-xl sm:p-10">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Sparkles className="size-4 text-brand-bright" aria-hidden="true" />
            Step {step} of 3
          </div>

          {step === 1 ? (
            <>
              <h1 className="mt-3 text-3xl font-extrabold tracking-tight">
                Welcome to HydraClip
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Turn a topic into a finished, scheduled video. Let’s set up your
                workspace in under a minute.
              </p>

              <div className="mt-6 space-y-3">
                <div className="space-y-1.5">
                  <Label htmlFor="onboarding-name">Your display name</Label>
                  <Input
                    id="onboarding-name"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="e.g. Jay"
                  />
                </div>
              </div>

              <div className="mt-6 flex justify-end">
                <Button onClick={() => setStep(2)}>
                  Continue
                  <ArrowRight className="size-4" />
                </Button>
              </div>
            </>
          ) : step === 2 ? (
            <>
              <h1 className="mt-3 text-3xl font-extrabold tracking-tight">
                What do you want to make?
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Tell us your first topic and we’ll spin up a project for you. You
                can generate the script, voiceover and render from there.
              </p>

              <div className="mt-6 space-y-3">
                <div className="space-y-1.5">
                  <Label htmlFor="onboarding-topic">Your first video topic</Label>
                  <Input
                    id="onboarding-topic"
                    value={firstTopic}
                    onChange={(event) => setFirstTopic(event.target.value)}
                    placeholder="e.g. 5 morning habits of successful founders"
                    maxLength={200}
                  />
                </div>

                <div className="grid gap-2 sm:grid-cols-2">
                  <button
                    type="button"
                    onClick={() => setFirstTopic("5 habits of calm people")}
                    className="rounded-lg border border-border bg-background p-3 text-left text-sm transition hover:border-ring"
                  >
                    <Wand2 className="mb-1 size-4 text-brand-bright" aria-hidden="true" />
                    <span className="font-medium">5 habits of calm people</span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">Self-improvement · short-form</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setFirstTopic("How compound interest actually works")}
                    className="rounded-lg border border-border bg-background p-3 text-left text-sm transition hover:border-ring"
                  >
                    <Clapperboard className="mb-1 size-4 text-brand-bright" aria-hidden="true" />
                    <span className="font-medium">How compound interest works</span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">Finance · long-form</span>
                  </button>
                </div>
              </div>

              {error && (
                <p role="alert" className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm">
                  {error}
                </p>
              )}

              <div className="mt-6 flex justify-between">
                <Button variant="ghost" onClick={() => setStep(1)}>
                  Back
                </Button>
                <Button onClick={() => void saveNameAndCreate()} disabled={creating}>
                  {creating ? "Creating…" : "Create my first project"}
                  <ArrowRight className="size-4" />
                </Button>
              </div>
            </>
          ) : (
            <>
              <h1 className="mt-3 text-3xl font-extrabold tracking-tight">
                You’re ready to ship
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                {firstTopic.trim()
                  ? "Project created. Connect a YouTube account to enable auto-publish, or just hit Generate to render a preview first."
                  : "Connect a YouTube account to enable auto-publish, or just hit Generate on your first project to render a preview."}
              </p>

              <ul className="mt-6 space-y-2 text-sm">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="size-4 text-emerald-500" aria-hidden="true" />
                  Account created
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="size-4 text-emerald-500" aria-hidden="true" />
                  Workspace ready
                </li>
                <li className="flex items-center gap-2">
                  <ArrowRight className="size-4 text-brand-bright" aria-hidden="true" />
                  Next: connect a platform
                </li>
              </ul>

              <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-end">
                <Button variant="outline" asChild>
                  <a href="/connect">Connect YouTube</a>
                </Button>
                <Button asChild>
                  <a href="/projects">Open projects</a>
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
