/**
 * Billing page: see the available plans, the caller's current subscription,
 * and open Stripe Checkout or the customer portal.
 *
 * Talks to /api/billing/overview, /api/billing/checkout and /api/billing/portal
 * via the same-origin proxy. When Stripe is not configured the buttons
 * still render but warn the user — this keeps the page useful in dev.
 */

import { SignedOutGuard, WorkspaceNav } from "@/components/WorkspaceNav";
import { Button } from "@/components/ui/button";
import { useAuthSession } from "@/auth-session";
import { api } from "@/lib/api";
import {
  CheckCircle2,
  CreditCard,
  Loader2,
  Sparkles,
  Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";

type Plan = {
  id: number;
  name: string;
  video_limit_monthly: number | null;
  storage_limit_gb: number | null;
  features: Record<string, unknown>;
  is_active: boolean;
  checkout_available: boolean;
};

type Subscription = {
  id: number;
  plan_id: number;
  plan_name?: string | null;
  status: string;
  current_period_end?: string | null;
  cancel_at_period_end?: boolean | null;
} | null;

type BillingOverview = {
  plans: Plan[];
  subscription: Subscription;
  stripe_configured: boolean;
  publishable_key: string;
};

export function BillingPage() {
  const session = useAuthSession();
  const signedIn = session.status === "authenticated";

  const [overview, setOverview] = useState<BillingOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"checkout" | "portal" | null>(null);

  useEffect(() => {
    if (!signedIn) return;
    void (async () => {
      try {
        setOverview(await api<BillingOverview>("/billing/overview"));
      } catch (caught) {
        setError(
          caught instanceof Error ? caught.message : "Could not load billing overview.",
        );
      }
    })();
  }, [signedIn]);

  if (!signedIn) return <SignedOutGuard page="Billing" />;

  async function startCheckout(planName: string) {
    setBusy("checkout");
    setError(null);
    try {
      const result = await api<{ checkout_url: string }>("/billing/checkout", {
        method: "POST",
        body: JSON.stringify({ plan_name: planName }),
      });
      window.location.assign(result.checkout_url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Checkout failed.");
      setBusy(null);
    }
  }

  async function openPortal() {
    setBusy("portal");
    setError(null);
    try {
      const result = await api<{ portal_url: string }>("/billing/portal", {
        method: "POST",
      });
      window.location.assign(result.portal_url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not open the portal.");
      setBusy(null);
    }
  }

  const currentPlanName = overview?.subscription?.plan_name ?? null;

  return (
    <main className="min-h-screen bg-background">
      <WorkspaceNav active="/billing" />
      <div className="mx-auto max-w-7xl space-y-10 px-6 py-10">
        <section aria-labelledby="billing-heading">
          <div className="flex items-center gap-2.5">
            <Wallet className="size-5 text-brand-bright" aria-hidden="true" />
            <h1 id="billing-heading" className="text-2xl font-bold tracking-tight">
              Billing
            </h1>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Pick a plan to unlock more videos, remove the watermark, and enable
            auto-publishing to YouTube.
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

        {overview?.subscription && (
          <section
            aria-labelledby="billing-current"
            className="rounded-2xl border border-border bg-card p-5"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm uppercase tracking-wide text-muted-foreground">
                  Current plan
                </p>
                <p className="mt-1 text-2xl font-bold">
                  {currentPlanName ?? overview.subscription.plan_id}
                  <span className="ml-2 align-middle text-xs font-normal text-muted-foreground">
                    {overview.subscription.status}
                  </span>
                </p>
                {overview.subscription.current_period_end && (
                  <p className="mt-1 text-sm text-muted-foreground">
                    Renews {new Date(overview.subscription.current_period_end).toLocaleDateString()}
                    {overview.subscription.cancel_at_period_end
                      ? " · cancels at period end"
                      : ""}
                  </p>
                )}
              </div>
              {overview.stripe_configured && (
                <Button
                  variant="outline"
                  disabled={busy !== null}
                  onClick={() => void openPortal()}
                >
                  {busy === "portal" ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <CreditCard className="size-4" />
                  )}
                  Manage in Stripe
                </Button>
              )}
            </div>
          </section>
        )}

        {!overview ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            Loading plans…
          </p>
        ) : (
          <section aria-labelledby="billing-plans">
            <h2 id="billing-plans" className="sr-only">
              Available plans
            </h2>
            <ul className="grid gap-4 md:grid-cols-3">
              {overview.plans.map((plan) => {
                const isCurrent = currentPlanName === plan.name;
                return (
                  <li
                    key={plan.id}
                    className={
                      isCurrent
                        ? "relative rounded-2xl border-2 border-ring bg-card p-6"
                        : "relative rounded-2xl border border-border bg-card p-6"
                    }
                  >
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="text-lg font-bold">{plan.name}</h3>
                      {isCurrent && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-medium text-emerald-500">
                          <CheckCircle2 className="size-3" aria-hidden="true" />
                          Current
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {plan.video_limit_monthly === null
                        ? "Unlimited videos / month"
                        : `${plan.video_limit_monthly} videos / month`}
                      {" · "}
                      {plan.storage_limit_gb === null
                        ? "Unlimited storage"
                        : `${plan.storage_limit_gb}GB storage`}
                    </p>

                    <Button
                      className="mt-5 w-full"
                      disabled={
                        isCurrent ||
                        !plan.checkout_available ||
                        busy !== null
                      }
                      onClick={() => void startCheckout(plan.name)}
                    >
                      {busy === "checkout" ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : isCurrent ? (
                        <CheckCircle2 className="size-4" />
                      ) : (
                        <Sparkles className="size-4" />
                      )}
                      {isCurrent
                        ? "Your plan"
                        : plan.checkout_available
                          ? `Upgrade to ${plan.name}`
                          : "Checkout unavailable"}
                    </Button>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        {!overview?.stripe_configured && overview && (
          <p className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
            Stripe is not configured on this deployment — plan upgrades are
            disabled. Set <code className="font-mono">STRIPE_SECRET_KEY</code> and
            the matching price IDs in the API container to enable Checkout.
          </p>
        )}
      </div>
    </main>
  );
}
