"use client";

import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clapperboard,
  Loader2,
  RefreshCw,
  Sparkles,
  Wand2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatLimit } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { GenerateForm } from "@/components/GenerateForm";
import { VideoCard } from "@/components/VideoCard";
import { StatCard } from "@/components/StatCard";
import { EmptyState } from "@/components/EmptyState";
import { ProgressBar } from "@/components/ProgressBar";

export default function StudioPage() {
  const { user } = useAuth();
  const { push } = useToast();

  const [videos, setVideos] = useState([]);
  const [jobs, setJobs] = useState({});
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const inFlight = useRef(false);

  const load = useCallback(async (showSpinner = false) => {
    if (inFlight.current) return;
    inFlight.current = true;
    if (showSpinner) setLoading(true);

    try {
      const [list, usageData] = await Promise.all([api.videos(), api.usage()]);
      setVideos(list);
      setUsage(usageData);

      const active = list.filter(
        (video) => video.status === "queued" || video.status === "generating",
      );
      const entries = await Promise.all(
        active.map(async (video) => {
          try {
            return [video.id, await api.status(video.id)];
          } catch {
            return null;
          }
        }),
      );
      setJobs(Object.fromEntries(entries.filter(Boolean)));
      setError("");
    } catch (err) {
      setError(err?.message || "Could not load your studio.");
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(true);
    const timer = setInterval(() => load(false), 4000);
    return () => clearInterval(timer);
  }, [load]);

  const stats = useMemo(() => {
    const completed = videos.filter((video) => video.status === "completed").length;
    const active = videos.filter(
      (video) => video.status === "queued" || video.status === "generating",
    ).length;
    const failed = videos.filter((video) => video.status === "failed").length;
    return { total: videos.length, completed, active, failed };
  }, [videos]);

  const usagePercent = useMemo(() => {
    if (!usage) return 0;
    if (usage.video_limit_monthly === -1) return 0;
    if (!usage.video_limit_monthly) return 0;
    return Math.min(
      100,
      (usage.videos_this_month / usage.video_limit_monthly) * 100,
    );
  }, [usage]);

  async function handleDelete(video) {
    const confirmed = window.confirm(
      `Delete “${video.title}”? This removes the video and its file.`,
    );
    if (!confirmed) return;

    try {
      await api.deleteVideo(video.id);
      setVideos((current) => current.filter((item) => item.id !== video.id));
      push("Video deleted.", "success");
    } catch (err) {
      push(err?.message || "Could not delete the video.", "error");
    }
  }

  async function handleDownload(video) {
    try {
      const result = await api.download(video.id);
      if (!result?.download_url) throw new Error("No download URL returned.");
      window.open(result.download_url, "_blank", "noopener,noreferrer");
    } catch (err) {
      push(err?.message || "The video file is not available.", "error");
    }
  }

  return (
    <div>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">
            Studio
          </p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-white">
            Welcome back, {user?.name?.split(" ")[0] || "creator"}
          </h1>
          <p className="mt-1 text-sm text-muted">
            Generate, monitor and download your AI shorts.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="badge border-line bg-panel2/70 text-slate-300">
            <Sparkles className="h-3.5 w-3.5 text-accent" />
            {usage ? (
              <>
                {usage.videos_this_month} / {formatLimit(usage.video_limit_monthly)}{" "}
                videos this month
              </>
            ) : (
              "Loading usage…"
            )}
          </span>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => load(true)}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {error ? (
        <div className="mt-5 flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="flex-1">
            <p>{error}</p>
            <button
              type="button"
              onClick={() => load(true)}
              className="mt-1 text-xs font-semibold underline underline-offset-2"
            >
              Try again
            </button>
          </div>
        </div>
      ) : null}

      <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
        <StatCard
          icon={Clapperboard}
          label="Videos"
          value={stats.total}
          hint="All time"
          tone="accent"
        />
        <StatCard
          icon={CheckCircle2}
          label="Completed"
          value={stats.completed}
          hint="Ready to download"
          tone="emerald"
        />
        <StatCard
          icon={Activity}
          label="Rendering"
          value={stats.active}
          hint="Queued or generating"
          tone="purple"
        />
        <StatCard
          icon={AlertTriangle}
          label="Failed"
          value={stats.failed}
          hint="Needs attention"
          tone="red"
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <section className="order-2 space-y-4 lg:order-1">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Your videos</h2>
              <p className="text-sm text-muted">
                {stats.active > 0
                  ? `${stats.active} rendering right now — this list updates automatically.`
                  : "Everything you have generated so far."}
              </p>
            </div>
            <Link href="#generate" className="btn btn-ghost btn-sm lg:hidden">
              <Wand2 className="h-3.5 w-3.5" />
              New
            </Link>
          </div>

          {loading && videos.length === 0 ? (
            <div className="card flex items-center justify-center gap-2 p-16 text-sm text-muted">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading videos…
            </div>
          ) : videos.length === 0 ? (
            <EmptyState
              icon={Clapperboard}
              title="No videos yet"
              description="Use the generator to queue your first short. HydraClip will plan, voice and render it in the background."
              action={
                <Link href="#generate" className="btn btn-primary btn-sm mt-1">
                  <Wand2 className="h-4 w-4" />
                  Generate your first video
                </Link>
              }
            />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {videos.map((video) => (
                <VideoCard
                  key={video.id}
                  video={video}
                  job={jobs[video.id]}
                  onDelete={handleDelete}
                  onDownload={handleDownload}
                />
              ))}
            </div>
          )}
        </section>

        <aside className="order-1 space-y-4 lg:order-2 lg:sticky lg:top-6 lg:self-start">
          <GenerateForm onGenerated={() => load(false)} />

          <div className="card p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">This month</h3>
              <Link
                href="/billing"
                className="text-xs font-semibold text-accent hover:text-accent/80"
              >
                Manage plan
              </Link>
            </div>

            <div className="mt-4 space-y-3">
              <div>
                <div className="flex items-center justify-between text-xs text-muted">
                  <span>Video quota</span>
                  <span className="font-mono text-slate-300">
                    {usage
                      ? `${usage.videos_this_month} / ${formatLimit(
                          usage.video_limit_monthly,
                        )}`
                      : "—"}
                  </span>
                </div>
                <ProgressBar value={usagePercent} className="mt-1.5" />
              </div>

              <div className="flex items-center justify-between text-xs">
                <span className="text-muted">Storage</span>
                <span className="font-mono text-slate-300">
                  {usage
                    ? `${usage.storage_used_gb} / ${usage.storage_limit_gb} GB`
                    : "—"}
                </span>
              </div>

              <div className="flex items-center justify-between text-xs">
                <span className="text-muted">Plan</span>
                <span className="font-semibold text-accent">
                  {user?.plan || "Free"}
                </span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
