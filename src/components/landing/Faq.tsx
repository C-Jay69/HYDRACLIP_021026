import { ChevronDown } from "lucide-react";

const FAQS = [
  {
    q: "Which AI models does it actually use?",
    a: "Scripts use OpenRouter Auto by default, fall back to NVIDIA NIM, and can optionally fall back to local Ollama. Narration uses Piper TTS and caption timing uses Whisper.",
  },
  {
    q: "Do I need a Shutterstock account?",
    a: "Only if you want the built-in stock library. Add a Shutterstock API token and search is available inside the editor; without one you can still upload your own footage and images.",
  },
  {
    q: "Can it really publish on its own?",
    a: "Yes for platforms that expose a publishing API under normal developer access. Where a platform does not allow it, HydraClip prepares the render, caption and metadata and hands you a one-tap manual upload instead of silently failing.",
  },
  {
    q: "Where are my videos stored?",
    a: "In your configured S3-compatible storage, including Supabase Storage, AWS S3, Cloudflare R2 or Spaces. Local disk mode is available for development.",
  },
  {
    q: "What happens if I go over my plan quota?",
    a: "Rendering pauses rather than billing you extra. Usage is tracked per account, shown on the dashboard, and you can upgrade at any point in the billing period.",
  },
] as const;

export function Faq() {
  return (
    <section id="faq" className="border-t border-border bg-surface px-6 py-20 md:py-28">
      <div className="mx-auto max-w-3xl">
        <div className="text-center">
          <p className="text-sm font-semibold tracking-wide text-brand-bright uppercase">FAQ</p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-balance sm:text-4xl">
            Questions worth asking first
          </h2>
        </div>

        <div className="mt-12 divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
          {FAQS.map((item) => (
            <details key={item.q} className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-6 py-5 font-medium transition-colors hover:bg-secondary/60 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
                {item.q}
                <ChevronDown
                  className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-open:rotate-180"
                  aria-hidden="true"
                />
              </summary>
              <p className="px-6 pb-5 text-sm leading-relaxed text-muted-foreground">{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
