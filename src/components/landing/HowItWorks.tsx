import mediaImage from "../../assets/feature-media.webp";
import scheduleImage from "../../assets/feature-schedule.webp";
import scriptImage from "../../assets/feature-script.webp";

type Step = {
  number: string;
  title: string;
  body: string;
  image: string;
  alt: string;
};

const STEPS: Step[] = [
  {
    number: "01",
    title: "Describe the video",
    body: "Type a topic, paste a URL or drop in your own script. A local LLM returns a structured draft you can edit line by line.",
    image: scriptImage,
    alt: "Script workspace with a prompt field above an AI-generated draft.",
  },
  {
    number: "02",
    title: "Pick the footage",
    body: "Search licensed stock images and video without leaving the editor, or upload your own assets. Voiceover and captions generate automatically.",
    image: mediaImage,
    alt: "Stock media browser showing a grid of licensable photo and video thumbnails.",
  },
  {
    number: "03",
    title: "Schedule and forget it",
    body: "Choose the platforms and the slots. Videoforce renders, uploads and publishes on time, then reports back on anything that failed.",
    image: scheduleImage,
    alt: "Weekly scheduling calendar with queued video posts and platform badges.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="border-t border-border bg-surface px-6 py-20 md:py-28">
      <div className="mx-auto max-w-7xl">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold tracking-wide text-brand-bright uppercase">How it works</p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-balance sm:text-4xl">
            Three steps from topic to timeline
          </h2>
        </div>

        <ol className="mt-14 grid grid-cols-1 gap-6 md:grid-cols-3">
          {STEPS.map((step) => (
            <li
              key={step.number}
              className="flex flex-col overflow-hidden rounded-xl border border-border bg-card transition-all duration-300 hover:-translate-y-1 hover:border-brand/60 hover:shadow-xl hover:shadow-brand/10"
            >
              <img
                src={step.image}
                alt={step.alt}
                width={1024}
                height={768}
                loading="lazy"
                decoding="async"
                className="aspect-4/3 w-full border-b border-border object-cover"
              />
              <div className="flex flex-1 flex-col p-6">
                <span className="font-mono text-sm font-semibold text-brand-bright">{step.number}</span>
                <h3 className="mt-2 text-lg font-semibold">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
