"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  Copy,
  Download,
  Loader2,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { StatusBadge } from "@/components/StatusBadge";
import { ProgressBar } from "@/components/ProgressBar";
import { formatDate, formatDuration } from "@/lib/format";

export default function VideoDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { push } = useToast();
  const id = params?.id;

  const [video, setVideo] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const load = useCallback(
    async (showSpinner = false) => {
      if (!id) return;
      if (showSpinner) setLoading(true);
      try {
        const [videoData, statusData] = await Promise.all([
          api.video(id),
          api.status(id),
        ]);
        setVideo(videoData);
        setStatus(statusData);
        setError("");
      } catch (err) {
        setError(err?.message || "Could not load this video.");
      } finally {
        setLoading(false);
      }
    },
    [id],
  );

  useEffect(() => {
    load(true);
  }, [load]);

  useEffect(() => {
    if (!video) return;
    if (video.status !== "queued" && video.status !== "generating") return;
    const timer = setInterval(() => load(false), 3000);
    return () => clearInterval(timer);
  }, [video, load]);

  async function handleDownload() {
    try {
      const result = await api.download(video.id);
      if (!result?.download_url) throw new Error("No download URL returned.");
      window.open(result.download_url, "_blank", "noopener,noreferrer");
    } catch (err) {
      push(err?.message || "The video file is not available.", "error");
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete “${video.title}”? This cannot be undone.`)) {
      return;
    }
    try {
      await api.deleteVideo(video.id);
      push("Video deleted.", "success");
      router.push("/");
    } catch (err) {
      push(err?.message || "Could not delete the video.", "error");
    }
  }

  async function copyScript() {
    if (!video?.script_text) return;
    try {
      await navigator.clipboard.writeText(video.script_text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
      push("Script copied.", "success");
    } catch {
      push("Could not copy the script.", "error");
    }
  }

  if (loading && !video) {
    return (
      <div className="card flex items-center justify-center gap-2 p-16 text-sm text-muted">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading video…
      </div>
    );
  }

  if (error && !video) {
    return (
      <div className="space-y-4">
        <Link href="/" className="btn btn-ghost btn-sm">
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to studio
        </Link>
        <div className="card flex flex-col items-center gap-3 p-12 text-center">
          <AlertTriangle className="h-8 w-8 text-red-300" />
          <h1 className="text-lg font-semibold text-white">
            Could not load video
          </h1>
          <p className="max-w-md text-sm text-muted">{error}</p>
        </div>
      </div>
    );
  }

  if (!video) return null;

  const job = status?.jobs?.[0];
  const progress =
    status?.progress ?? (video.status === "completed" ? 100 : 0);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <Link href="/" className="btn btn-ghost btn-sm">
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to studio
        </Link>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => load(true)}
          disabled={loading}
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            {video.title}
          </h1>
          <p className="mt-1 text-sm text-muted">
            {video.description || "No description"}
          </p>
        </div>
        <StatusBadge status={video.status} />
      </header>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-5">
          <section className="card p-5">
            <div className="flex items-center justify-between text-sm">
              <span className="font-semibold text-white">
                {video.status === "completed"
                  ? "Render complete"
                  : video.status === "failed"
                    ? "Render failed"
                    : "Render progress"}
              </span>
              <span className="font-mono text-slate-300">
                {Math.round(progress)}%
              </span>
            </div>
            <ProgressBar
              value={progress}
              active={video.status === "queued" || video.status === "generating"}
              className="mt-2.5"
            />

            {job ? (
              <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
                <div className="rounded-xl border border-line bg-ink/40 p-3">
                  <dt className="text-muted">Job status</dt>
                  <dd className="mt-1 font-semibold capitalize text-slate-200">
                    {job.status}
                  </dd>
                </div>
                <div className="rounded-xl border border-line bg-ink/40 p-3">
                  <dt className="text-muted">Started</dt>
                  <dd className="mt-1 text-slate-200">
                    {formatDate(job.started_at)}
                  </dd>
                </div>
                <div className="rounded-xl border border-line bg-ink/40 p-3">
                  <dt className="text-muted">Completed</dt>
                  <dd className="mt-1 text-slate-200">
                    {formatDate(job.completed_at)}
                  </dd>
                </div>
                <div className="rounded-xl border border-line bg-ink/40 p-3">
                  <dt className="text-muted">Job type</dt>
                  <dd className="mt-1 capitalize text-slate-200">
                    {job.job_type?.replace(/_/g, " ")}
                  </dd>
                </div>
              </dl>
            ) : null}

            {video.error_message || job?.error_message ? (
              <div className="mt-4 flex items-start gap-2 rounded-xl border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-300">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{video.error_message || job?.error_message}</span>
              </div>
            ) : null}

            {(video.status === "queued" || video.status === "generating") && (
              <p className="mt-3 text-xs text-muted">
                Rendering is CPU-bound. This page refreshes automatically every
                few seconds.
              </p>
            )}
          </section>

          <section className="card p-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-white">Script</h2>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={copyScript}
                disabled={!video.script_text}
              >
                {copied ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <pre className="mt-3 max-h-[420px] overflow-auto whitespace-pre-wrap break-words rounded-xl border border-line bg-ink/50 p-4 text-sm leading-relaxed text-slate-300">
              {video.script_text || "The script will appear here once planning finishes."}
            </pre>
          </section>
        </div>

        <aside className="space-y-4">
          <section className="card p-5">
            <h2 className="text-sm font-semibold text-white">Details</h2>
            <dl className="mt-3 space-y-2.5 text-xs">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-muted">Created</dt>
                <dd className="text-right text-slate-200">
                  {formatDate(video.created_at)}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-muted">Duration</dt>
                <dd className="text-right font-mono text-slate-200">
                  {formatDuration(video.duration_seconds)}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-muted">Resolution</dt>
                <dd className="text-right font-mono text-slate-200">
                  {video.resolution || "—"}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-muted">Format</dt>
                <dd className="text-right font-mono uppercase text-slate-200">
                  {video.format || "—"}
                </dd>
              </div>
            </dl>

            <div className="mt-4 space-y-2">
              <button
                type="button"
                className="btn btn-primary w-full"
                onClick={handleDownload}
                disabled={video.status !== "completed"}
              >
                <Download className="h-4 w-4" />
                Download MP4
              </button>
              <button
                type="button"
                className="btn btn-danger w-full"
                onClick={handleDelete}
              >
                <Trash2 className="h-4 w-4" />
                Delete video
              </button>
            </div>
          </section>

          <section className="card p-5">
            <h2 className="text-sm font-semibold text-white">What happens next</h2>
            <p className="mt-2 text-xs leading-relaxed text-muted">
              Once the render is complete you can download the MP4 or schedule it
              for publishing from the{" "}
              <Link href="/schedules" className="text-accent hover:underline">
                Schedules
              </Link>{" "}
              page.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
