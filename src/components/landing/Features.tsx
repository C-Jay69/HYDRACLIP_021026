import { AudioLines, CalendarClock, Clapperboard, ImageIcon, Server, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";

type Feature = {
  icon: LucideIcon;
  title: string;
  body: string;
};

const FEATURES: Feature[] = [
  {
    icon: Clapperboard,
    title: "Script generation",
    body: "Give it a topic and OpenRouter drafts a hook, body and call to action, with NVIDIA NIM ready if the primary provider is unavailable.",
  },
  {
    icon: ImageIcon,
    title: "Licensed stock media",
    body: "Search Shutterstock images and video from inside the editor, with licence type and price shown before you commit.",
  },
  {
    icon: AudioLines,
    title: "Voiceover and music",
    body: "Piper handles text-to-speech and Whisper aligns captions, so narration and subtitles stay in sync without a studio.",
  },
  {
    icon: CalendarClock,
    title: "Scheduling and auto-publish",
    body: "Queue a video once and it posts itself to YouTube, Instagram, TikTok and X, with a manual fallback where an API will not allow it.",
  },
  {
    icon: Server,
    title: "Resilient AI pipeline",
    body: "OpenRouter is the default, NVIDIA NIM is the automatic backup, and local Ollama remains available as an opt-in fallback.",
  },
  {
    icon: ShieldCheck,
    title: "Built for teams",
    body: "Role-based access, per-plan usage quotas and an audit log of every admin action, backed by Postgres and S3-compatible storage.",
  },
];

export function Features() {
  return (
    <section id="features" className="border-t border-border px-6 py-20 md:py-28">
      <div className="mx-auto max-w-7xl">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold tracking-wide text-brand-bright uppercase">Features</p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-balance sm:text-4xl">
            Everything between an idea and a post
          </h2>
          <p className="mt-4 text-pretty text-muted-foreground">
            One pipeline covers writing, footage, audio, rendering and distribution — so there is no
            handoff between six different tools.
          </p>
        </div>

        <ul className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <li
              key={title}
              className="group rounded-xl border border-border bg-card p-6 transition-all duration-300 hover:-translate-y-1 hover:border-brand/60 hover:shadow-xl hover:shadow-brand/10"
            >
              <span className="inline-flex size-11 items-center justify-center rounded-lg bg-brand/15 text-brand-bright ring-1 ring-brand/25">
                <Icon className="size-5" aria-hidden="true" />
              </span>
              <h3 className="mt-5 text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
