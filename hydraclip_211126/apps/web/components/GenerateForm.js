"use client";

import { useState } from "react";
import { Clock, Loader2, Sparkles, Wand2 } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "./Toast";

const examples = [
  {
    label: "Octopus intelligence",
    title: "The Secret Life of Octopuses",
    topic: "why octopuses are the smartest animals in the ocean",
  },
  {
    label: "Bioluminescence",
    title: "How Bioluminescence Works",
    topic: "how deep sea creatures make their own light",
  },
  {
    label: "Focus habits",
    title: "3 Habits That Improve Focus",
    topic: "three simple habits that improve focus",
  },
];

export function GenerateForm({ onGenerated }) {
  const { push } = useToast();
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return;

    if (!title.trim() || !topic.trim()) {
      push("Add a title and a topic first.", "warning");
      return;
    }

    setSubmitting(true);
    try {
      const video = await api.generate(title.trim(), topic.trim());
      push("Video queued. Rendering started in the background.", "success");
      setTitle("");
      setTopic("");
      onGenerated?.(video);
    } catch (error) {
      push(error?.message || "Could not queue the video.", "error");
    } finally {
      setSubmitting(false);
    }
  }

  function useExample(example) {
    setTitle(example.title);
    setTopic(example.topic);
  }

  return (
    <section id="generate" className="card scroll-mt-24 p-5 sm:p-6">
      <div className="flex items-start gap-3">
        <span className="rounded-xl border border-accent/20 bg-accent/10 p-2 text-accent">
          <Wand2 className="h-5 w-5" />
        </span>
        <div>
          <h2 className="text-lg font-semibold text-white">Generate a short</h2>
          <p className="mt-0.5 text-sm text-muted">
            Give it a title and a topic. HydraClip plans, voices and renders it.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="mt-5 space-y-4">
        <div>
          <label className="label" htmlFor="video-title">
            Title
          </label>
          <input
            id="video-title"
            className="input"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="The Secret Life of Octopuses"
            maxLength={120}
          />
        </div>

        <div>
          <label className="label" htmlFor="video-topic">
            Topic
          </label>
          <textarea
            id="video-topic"
            className="input min-h-[92px] resize-y"
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            placeholder="why octopuses are the smartest animals in the ocean"
            maxLength={500}
          />
        </div>

        <div>
          <span className="label">Try an example</span>
          <div className="flex flex-wrap gap-2">
            {examples.map((example) => (
              <button
                key={example.label}
                type="button"
                onClick={() => useExample(example)}
                className="rounded-full border border-line bg-panel2/60 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:border-accent/40 hover:text-white"
              >
                {example.label}
              </button>
            ))}
          </div>
        </div>

        <button
          type="submit"
          className="btn btn-primary w-full"
          disabled={submitting}
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Queueing…
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              Generate video
            </>
          )}
        </button>
      </form>

      <div className="mt-4 flex items-start gap-2 rounded-xl border border-line bg-ink/40 p-3 text-xs leading-relaxed text-muted">
        <Clock className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span>
          Generation runs in the background. Rendering is CPU-bound and usually
          takes a few minutes per short.
        </span>
      </div>
    </section>
  );
}
