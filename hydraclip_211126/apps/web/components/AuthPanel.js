"use client";

import { useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Loader2,
  Sparkles,
  Video,
  Wand2,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const features = [
  {
    icon: Wand2,
    title: "OpenRouter planning",
    text: "Scripts and scene plans generated for every topic.",
  },
  {
    icon: Video,
    title: "Remotion rendering",
    text: "1080×1920 MP4s rendered by your own worker.",
  },
  {
    icon: CheckCircle2,
    title: "Schedule & publish",
    text: "Queue videos and publish when they are ready.",
  },
];

export function AuthPanel() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const isRegister = mode === "register";

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !password) {
      setError("Email and password are required.");
      return;
    }
    if (isRegister && !name.trim()) {
      setError("Please enter your name.");
      return;
    }
    if (isRegister && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setSubmitting(true);
    try {
      if (isRegister) {
        await register(name.trim(), trimmedEmail, password);
      } else {
        await login(trimmedEmail, password);
      }
    } catch (err) {
      setError(
        err?.status === 429
          ? "Too many attempts. Wait a minute and try again."
          : err?.message || "Something went wrong.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  function switchMode(next) {
    setMode(next);
    setError("");
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-hero">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_120%,rgba(53,242,193,0.08),transparent_55%)]" />

      <div className="relative mx-auto grid min-h-screen max-w-6xl items-center gap-12 px-6 py-12 lg:grid-cols-[1.1fr_0.9fr] lg:px-10">
        <section className="hidden lg:block">
          <div className="inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-accent">
            <Sparkles className="h-3.5 w-3.5" />
            AI video studio
          </div>
          <h1 className="mt-6 text-5xl font-bold leading-[1.05] tracking-tight text-white">
            Turn a topic into a
            <span className="bg-gradient-to-r from-accent to-accent2 bg-clip-text text-transparent">
              {" "}
              finished short.
            </span>
          </h1>
          <p className="mt-5 max-w-lg text-base leading-relaxed text-muted">
            HydraClip plans the script with OpenRouter, voices it locally, renders
            it with Remotion, and gives you an MP4 you can download or schedule.
          </p>

          <div className="mt-9 grid gap-4 sm:grid-cols-3">
            {features.map((feature) => (
              <div key={feature.title} className="card p-4">
                <feature.icon className="h-5 w-5 text-accent" />
                <h3 className="mt-3 text-sm font-semibold text-white">
                  {feature.title}
                </h3>
                <p className="mt-1 text-xs leading-relaxed text-muted">
                  {feature.text}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto w-full max-w-md">
          <div className="mb-8 flex items-center gap-2 lg:hidden">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-accent2 text-ink">
              <Sparkles className="h-5 w-5" />
            </span>
            <span className="text-lg font-bold text-white">HydraClip</span>
          </div>

          <div className="card p-6 sm:p-8">
            <div className="flex rounded-xl border border-line bg-ink/60 p-1">
              <button
                type="button"
                onClick={() => switchMode("login")}
                className={`flex-1 rounded-lg px-3 py-2 text-sm font-semibold transition ${
                  !isRegister
                    ? "bg-panel2 text-white shadow"
                    : "text-muted hover:text-white"
                }`}
              >
                Sign in
              </button>
              <button
                type="button"
                onClick={() => switchMode("register")}
                className={`flex-1 rounded-lg px-3 py-2 text-sm font-semibold transition ${
                  isRegister
                    ? "bg-panel2 text-white shadow"
                    : "text-muted hover:text-white"
                }`}
              >
                Create account
              </button>
            </div>

            <div className="mt-6">
              <h2 className="text-xl font-semibold text-white">
                {isRegister ? "Start creating" : "Welcome back"}
              </h2>
              <p className="mt-1 text-sm text-muted">
                {isRegister
                  ? "Create an account to generate your first video."
                  : "Sign in to your HydraClip studio."}
              </p>
            </div>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              {isRegister ? (
                <div>
                  <label className="label" htmlFor="name">
                    Name
                  </label>
                  <input
                    id="name"
                    className="input"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="Alex Creator"
                    autoComplete="name"
                  />
                </div>
              ) : null}

              <div>
                <label className="label" htmlFor="email">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  className="input"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                />
              </div>

              <div>
                <label className="label" htmlFor="password">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  className="input"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder={isRegister ? "At least 8 characters" : "••••••••"}
                  autoComplete={isRegister ? "new-password" : "current-password"}
                />
              </div>

              {error ? (
                <div className="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              ) : null}

              <button
                type="submit"
                className="btn btn-primary w-full"
                disabled={submitting}
              >
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {isRegister ? "Creating account…" : "Signing in…"}
                  </>
                ) : (
                  <>
                    {isRegister ? "Create account" : "Sign in"}
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </form>

            <div className="mt-6 rounded-xl border border-line bg-ink/40 p-3 text-xs text-muted">
              <p className="font-semibold text-slate-300">Demo account</p>
              <p className="mt-1">
                <span className="kbd">test@example.com</span>{" "}
                <span className="kbd">testpassword123</span>
              </p>
            </div>
          </div>

          <p className="mt-6 text-center text-xs text-muted">
            Generation is CPU-rendered and can take a few minutes per video.
          </p>
        </section>
      </div>
    </div>
  );
}
