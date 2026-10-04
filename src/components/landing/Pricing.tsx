import { useAuthSession } from "@/auth-session";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Check, Minus } from "lucide-react";
import { useState } from "react";

type Billing = "monthly" | "annual";

type Plan = {
  /** Matches `name` in backend/seed.py */
  name: string;
  tagline: string;
  monthly: number;
  /** Quotas mirror the Plan rows created by seed.py. */
  features: { label: string; included: boolean }[];
  cta: string;
  featured?: boolean;
};

const PLANS: Plan[] = [
  {
    name: "Free",
    tagline: "Kick the tyres on the full pipeline.",
    monthly: 0,
    features: [
      { label: "3 videos per month", included: true },
      { label: "1 GB asset storage", included: true },
      { label: "AI script, neural voice and captions", included: true },
      { label: "Watermark-free exports", included: false },
      { label: "Scheduled auto-publishing", included: false },
    ],
    cta: "Start for free",
  },
  {
    name: "Creator",
    tagline: "For one person shipping on a schedule.",
    monthly: 19,
    features: [
      { label: "25 videos per month", included: true },
      { label: "10 GB asset storage", included: true },
      { label: "Watermark-free exports", included: true },
      { label: "Scheduled auto-publishing", included: true },
      { label: "Direct YouTube publishing", included: true },
    ],
    cta: "Choose Creator",
    featured: true,
  },
  {
    name: "Pro",
    tagline: "For teams and agencies running volume.",
    monthly: 49,
    features: [
      { label: "Unlimited videos", included: true },
      { label: "50 GB asset storage", included: true },
      { label: "Watermark-free exports", included: true },
      { label: "All four publishing destinations", included: true },
      { label: "Priority render queue", included: true },
    ],
    cta: "Choose Pro",
  },
];

export function Pricing() {
  const [billing, setBilling] = useState<Billing>("monthly");
  const session = useAuthSession();
  const signedIn = session.status === "authenticated";

  return (
    <section id="pricing" className="border-t border-border px-6 py-20 md:py-28">
      <div className="mx-auto max-w-7xl">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold tracking-wide text-brand-bright uppercase">Pricing</p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-balance sm:text-4xl">
            Simple plans, no surprise render bills
          </h2>
          <p className="mt-4 text-pretty text-muted-foreground">
            Because generation runs on self-hosted open models, you are paying for the platform — not
            per token or per second of footage.
          </p>
        </div>

        <div
          role="group"
          aria-label="Billing period"
          className="mx-auto mt-10 flex w-fit items-center gap-1 rounded-full border border-border bg-card p-1"
        >
          {(["monthly", "annual"] as const).map((period) => (
            <button
              key={period}
              type="button"
              aria-pressed={billing === period}
              onClick={() => setBilling(period)}
              className={cn(
                "rounded-full px-4 py-1.5 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                billing === period
                  ? "bg-brand text-brand-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {period === "monthly" ? "Monthly" : "Annual"}
              {period === "annual" && (
                <span className="ml-1.5 text-xs opacity-80">· 2 months free</span>
              )}
            </button>
          ))}
        </div>

        <div className="mt-12 grid grid-cols-1 items-start gap-6 lg:grid-cols-3">
          {PLANS.map((plan) => {
            const price = billing === "annual" ? Math.round((plan.monthly * 10) / 12) : plan.monthly;

            return (
              <div
                key={plan.name}
                className={cn(
                  "relative flex flex-col rounded-2xl border bg-card p-7",
                  plan.featured
                    ? "border-brand/70 shadow-2xl shadow-brand/15 lg:-mt-4 lg:pt-10 lg:pb-10"
                    : "border-border",
                )}
              >
                {plan.featured && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-brand px-3 py-1 text-xs font-semibold text-brand-foreground">
                    Most popular
                  </span>
                )}

                <h3 className="text-lg font-semibold">{plan.name}</h3>
                <p className="mt-1.5 text-sm text-muted-foreground">{plan.tagline}</p>

                <p className="mt-6 flex items-baseline gap-1.5">
                  <span className="text-4xl font-extrabold tracking-tight">${price}</span>
                  <span className="text-sm text-muted-foreground">
                    {plan.monthly === 0 ? "forever" : "/ month"}
                  </span>
                </p>
                {plan.monthly > 0 && billing === "annual" && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Billed ${plan.monthly * 10} once a year
                  </p>
                )}

                <ul className="mt-7 flex-1 space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature.label} className="flex items-start gap-2.5 text-sm">
                      {feature.included ? (
                        <Check className="mt-0.5 size-4 shrink-0 text-brand-bright" aria-hidden="true" />
                      ) : (
                        <Minus className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                      )}
                      <span className={feature.included ? undefined : "text-muted-foreground"}>
                        {feature.label}
                        <span className="sr-only">{feature.included ? " — included" : " — not included"}</span>
                      </span>
                    </li>
                  ))}
                </ul>

                <Button
                  className="mt-8 w-full"
                  variant={plan.featured ? "default" : "outline"}
                  asChild
                >
                  <a href={signedIn ? "/dashboard" : "/auth?mode=signup"}>
                    {signedIn ? "Open your dashboard" : plan.cta}
                  </a>
                </Button>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
