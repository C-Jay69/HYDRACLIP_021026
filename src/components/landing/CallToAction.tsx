import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";
import { useState, type FormEvent } from "react";

export function CallToAction() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!email.trim()) return;
    // No signup endpoint exists yet — acknowledge locally rather than
    // pretending to POST somewhere that would 404.
    setSubmitted(true);
  };

  return (
    <section id="cta" className="border-t border-border px-6 py-20 md:py-28">
      <div className="relative mx-auto max-w-4xl overflow-hidden rounded-2xl border border-brand/40 bg-card px-6 py-14 text-center sm:px-12">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_70%_60%_at_50%_0%,rgba(168,85,247,0.22),transparent_70%)]"
        />

        <div className="relative">
          <h2 className="text-3xl font-bold tracking-tight text-balance sm:text-4xl">
            Your next twelve videos, already scheduled
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-pretty text-muted-foreground">
            Start on the free plan — three videos a month, the whole pipeline, no card required.
          </p>

          {submitted ? (
            <p
              role="status"
              className="mx-auto mt-8 max-w-md rounded-lg border border-brand/40 bg-brand/10 px-4 py-3 text-sm"
            >
              Thanks — we have noted <span className="font-medium">{email}</span>. Account signup
              lands with the authentication service.
            </p>
          ) : (
            <form
              onSubmit={handleSubmit}
              className="mx-auto mt-8 flex max-w-md flex-col gap-3 sm:flex-row"
            >
              <label htmlFor="cta-email" className="sr-only">
                Work email
              </label>
              <input
                id="cta-email"
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@studio.com"
                className="h-11 flex-1 rounded-md border border-input bg-background px-3.5 text-sm placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
              />
              <Button type="submit" size="lg">
                Get started
                <ArrowRight className="size-4" aria-hidden="true" />
              </Button>
            </form>
          )}

          <p className="mt-4 text-xs text-muted-foreground">
            Free forever plan · No credit card · Self-hostable
          </p>
        </div>
      </div>
    </section>
  );
}
