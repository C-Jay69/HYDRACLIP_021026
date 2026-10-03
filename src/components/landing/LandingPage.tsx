import { StockMediaBrowser } from "@/components/StockMediaBrowser";

import { CallToAction } from "./CallToAction";
import { Faq } from "./Faq";
import { Features } from "./Features";
import { Hero } from "./Hero";
import { HowItWorks } from "./HowItWorks";
import { Pricing } from "./Pricing";
import { SiteFooter } from "./SiteFooter";
import { SiteHeader } from "./SiteHeader";
import { Stats } from "./Stats";

export function LandingPage() {
  return (
    <>
      {/*
        Decorative layers are SIBLINGS of the content, not ancestors of it.
        When they wrapped the page, their `opacity`, `pointer-events: none`
        and negative z-index applied to every section inside them and the whole
        site rendered invisible and unclickable.
      */}
      <div aria-hidden="true" className="vf-aurora pointer-events-none fixed inset-0 z-0" />
      <div aria-hidden="true" className="vf-noise pointer-events-none fixed inset-0 z-0" />

      <div className="relative z-10 flex min-h-screen flex-col">
        <a
          href="#main"
          className="sr-only rounded-md bg-brand px-4 py-2 text-brand-foreground focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-[60]"
        >
          Skip to content
        </a>

        <SiteHeader />

        <main id="main" className="flex-1">
          <Hero />
          <Stats />
          <Features />
          <HowItWorks />

          <section id="demo" className="border-t border-border px-6 py-20 md:py-28">
            <div className="mx-auto max-w-7xl">
              <div className="mx-auto max-w-2xl text-center">
                <p className="text-sm font-semibold tracking-wide text-brand-bright uppercase">
                  Live demo
                </p>
                <h2 className="mt-3 text-3xl font-bold tracking-tight text-balance sm:text-4xl">
                  Search the stock library
                </h2>
                <p className="mt-4 text-pretty text-muted-foreground">
                  The same browser creators use inside the editor. Add a Shutterstock API token to
                  query the live catalogue — otherwise it returns sample results.
                </p>
              </div>

              <div className="mt-12 rounded-2xl border border-border bg-card p-4 sm:p-6">
                <StockMediaBrowser />
              </div>
            </div>
          </section>

          <Pricing />
          <Faq />
          <CallToAction />
        </main>

        <SiteFooter />
      </div>
    </>
  );
}
