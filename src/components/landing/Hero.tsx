import { Button } from "@/components/ui/button";
import { ArrowRight, PlayCircle, Sparkles } from "lucide-react";

import heroImage from "../../assets/hero-dashboard.webp";
import { PLATFORM_LABELS, PlatformIcon, type Platform } from "./PlatformIcon";

const PLATFORMS: Platform[] = ["youtube", "instagram", "tiktok", "x"];

export function Hero() {
  return (
    <section id="top" className="relative px-6 pt-20 pb-16 md:pt-28 md:pb-24">
      <div className="mx-auto max-w-7xl">
        <div className="mx-auto max-w-3xl text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3.5 py-1.5 text-xs font-medium text-muted-foreground">
            <Sparkles className="size-3.5 text-brand-bright" aria-hidden="true" />
            Runs on local, open-source models — no paid model APIs
          </span>

          <h1 className="mt-6 text-4xl leading-[1.08] font-extrabold tracking-tight text-balance sm:text-5xl lg:text-6xl">
            Turn a topic into a <span className="hc-gradient-text">published video</span>.
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg text-pretty text-muted-foreground">
            HydraClip writes the script, picks the footage, records the voiceover and schedules the
            upload — to YouTube, Instagram, TikTok and X. Everything generated locally, every clip
            properly licensed.
          </p>

          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button size="lg" className="w-full sm:w-auto" asChild>
              <a href="#pricing">
                Start creating free
                <ArrowRight className="size-4" aria-hidden="true" />
              </a>
            </Button>
            <Button size="lg" variant="outline" className="w-full sm:w-auto" asChild>
              <a href="#how-it-works">
                <PlayCircle className="size-4" aria-hidden="true" />
                See how it works
              </a>
            </Button>
          </div>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-3">
            <span className="text-xs tracking-wide text-muted-foreground uppercase">Publishes to</span>
            {PLATFORMS.map((platform) => (
              <span key={platform} className="flex items-center gap-2 text-sm text-muted-foreground">
                <PlatformIcon platform={platform} className="size-4.5" />
                {PLATFORM_LABELS[platform]}
              </span>
            ))}
          </div>
        </div>

        <div className="relative mt-16 md:mt-20">
          <div
            aria-hidden="true"
            className="absolute -inset-x-10 -top-10 bottom-10 rounded-[2.5rem] bg-brand/25 blur-3xl"
          />
          <div className="hc-float relative overflow-hidden rounded-2xl border border-border bg-card shadow-2xl shadow-black/60">
            <img
              src={heroImage}
              alt="The HydraClip dashboard showing a publishing calendar filled with scheduled video posts alongside performance charts."
              width={1600}
              height={900}
              loading="eager"
              decoding="async"
              className="block h-auto w-full"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
