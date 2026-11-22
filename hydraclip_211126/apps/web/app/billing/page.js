"use client";

import { useEffect, useState } from "react";
import {
  Check,
  CreditCard,
  ExternalLink,
  Gauge,
  Loader2,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/Toast";
import { formatLimit, parseFeatures } from "@/lib/format";

export default function BillingPage() {
  const { user } = useAuth();
  const { push } = useToast();

  const [plans, setPlans] = useState([]);
  const [subscription, setSubscription] = useState(null);
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [planList, sub, usageData] = await Promise.all([
          api.plans(),
          api.subscription(),
          api.usage(),
        ]);
        if (!active) return;
        setPlans(planList);
        setSubscription(sub);
        setUsage(usageData);
      } catch (err) {
        if (active) push(err?.message || "Could not load billing.", "error");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [push]);

  const currentPlan = (
    subscription?.plan ||
    user?.plan ||
    "Free"
  ).toLowerCase();

  async function handleCheckout(plan) {
    setBusy(plan.id);
    try {
      const result = await api.checkout(plan.id);
      if (result?.checkout_url) {
        window.open(result.checkout_url, "_blank", "noopener,noreferrer");
        push("Checkout opened in a new tab.", "success");
      } else {
        push("Checkout is not configured yet.", "warning");
      }
    } catch (err) {
      push(err?.message || "Could not start checkout.", "error");
    } finally {
      setBusy("");
    }
  }

  async function handlePortal() {
    setBusy("portal");
    try {
      const result = await api.portal();
      if (result?.portal_url) {
        window.open(result.portal_url, "_blank", "noopener,noreferrer");
      } else {
        push("Billing portal is not configured yet.", "warning");
      }
    } catch (err) {
      push(err?.message || "Could not open the billing portal.", "error");
    } finally {
      setBusy("");
    }
  }

  if (loading) {
    return (
      <div className="card flex items-center justify-center gap-2 p-16 text-sm text-muted">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading plans…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">
          Billing
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-white">
          Plans & usage
        </h1>
        <p className="mt-1 text-sm text-muted">
          Upgrade for more videos and storage. Plans are billed monthly.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="card p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted">
              Current plan
            </span>
            <CreditCard className="h-4 w-4 text-accent" />
          </div>
          <p className="mt-3 text-2xl font-bold text-white">
            {subscription?.plan || user?.plan || "Free"}
          </p>
          <p className="mt-1 text-xs text-muted">
            Status: {subscription?.status || "active"}
          </p>
        </div>

        <div className="card p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted">
              Video quota
            </span>
            <Gauge className="h-4 w-4 text-accent2" />
          </div>
          <p className="mt-3 text-2xl font-bold text-white">
            {usage ? `${usage.videos_this_month} / ${formatLimit(usage.video_limit_monthly)}` : "—"}
          </p>
          <p className="mt-1 text-xs text-muted">Videos this month</p>
        </div>

        <div className="card p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted">
              Storage
            </span>
            <Sparkles className="h-4 w-4 text-emerald-300" />
          </div>
          <p className="mt-3 text-2xl font-bold text-white">
            {usage ? `${usage.storage_used_gb} / ${usage.storage_limit_gb} GB` : "—"}
          </p>
          <p className="mt-1 text-xs text-muted">Rendered video storage</p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {plans.map((plan) => {
          const isCurrent = plan.name.toLowerCase() === currentPlan;
          const features = parseFeatures(plan.features_json);
          const price =
            plan.price_display ||
            `$${((plan.price_cents || 0) / 100).toFixed(2)}`;

          return (
            <div
              key={plan.id}
              className={`card flex flex-col p-5 ${
                isCurrent ? "border-accent/40 shadow-glow" : ""
              }`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-white">
                    {plan.name}
                  </h2>
                  <p className="mt-1 text-xs text-muted">
                    {formatLimit(plan.video_limit_monthly)} videos ·{" "}
                    {plan.storage_limit_gb} GB storage
                  </p>
                </div>
                {isCurrent ? (
                  <span className="badge border-accent/30 bg-accent/10 text-accent">
                    Current
                  </span>
                ) : null}
              </div>

              <p className="mt-5">
                <span className="text-3xl font-bold text-white">{price}</span>
                <span className="ml-1 text-xs text-muted">/ month</span>
              </p>

              <ul className="mt-4 flex-1 space-y-2 text-sm text-slate-300">
                {features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>

              <button
                type="button"
                className={`btn mt-5 w-full ${
                  isCurrent ? "btn-ghost" : "btn-primary"
                }`}
                disabled={isCurrent || busy === plan.id}
                onClick={() => handleCheckout(plan)}
              >
                {busy === plan.id ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ExternalLink className="h-4 w-4" />
                )}
                {isCurrent ? "Current plan" : `Choose ${plan.name}`}
              </button>
            </div>
          );
        })}
      </div>

      <div className="card flex flex-col items-start justify-between gap-3 p-5 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-sm font-semibold text-white">Manage subscription</h2>
          <p className="mt-1 text-xs text-muted">
            Open the Stripe customer portal to update payment details or cancel.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={handlePortal}
          disabled={busy === "portal"}
        >
          {busy === "portal" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <CreditCard className="h-4 w-4" />
          )}
          Open portal
        </button>
      </div>

      <p className="text-xs text-muted">
        Checkout and the billing portal are mocked until live Stripe keys are
        configured in <span className="kbd">.env</span>.
      </p>
    </div>
  );
}
