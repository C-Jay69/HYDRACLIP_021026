"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ChevronRight,
  Clock,
  Download,
  Film,
  Trash2,
} from "lucide-react";
import { StatusBadge } from "./StatusBadge";
import { ProgressBar } from "./ProgressBar";
import { formatDate, formatDuration, timeAgo } from "@/lib/format";

export function VideoCard({ video, job, onDelete, onDownload }) {
  const active = video.status === "queued" || video.status === "generating";
  const progress = job?.progress ?? (video.status === "completed" ? 100 : 0);
  const jobRunning = job?.status === "running";

  return (
    <article className="card card-hover flex flex-col gap-4 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            href={`/videos/${video.id}`}
            className="block truncate text-base font-semibold text-white transition hover:text-accent"
            title={video.title}
          >
            {video.title}
          </Link>
          <p className="mt-1 line-clamp-2 text-sm text-muted">
            {video.description || "No description"}
          </p>
        </div>
        <StatusBadge status={video.status} />
      </div>

      {active ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-muted">
            <span className="inline-flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" />
              {jobRunning ? "Rendering…" : "Queued…"}
            </span>
            <span className="font-mono text-slate-300">
              {Math.round(progress)}%
            </span>
          </div>
          <ProgressBar value={progress} active />
          <p className="text-xs text-muted">
            Rendering runs on your worker; this page updates automatically.
          </p>
        </div>
      ) : null}

      {video.status === "completed" ? (
        <div className="flex flex-wrap gap-2 text-xs text-slate-300">
          <span className="rounded-lg border border-line bg-ink/50 px-2 py-1">
            <Film className="mr-1 inline h-3 w-3" />
            {video.resolution || "1080x1920"}
          </span>
          <span className="rounded-lg border border-line bg-ink/50 px-2 py-1">
            {formatDuration(video.duration_seconds)}
          </span>
          <span className="rounded-lg border border-line bg-ink/50 px-2 py-1 uppercase">
            {video.format || "mp4"}
          </span>
        </div>
      ) : null}

      {video.status === "failed" ? (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-300">
          <p className="inline-flex items-center gap-1.5 font-semibold">
            <AlertTriangle className="h-3.5 w-3.5" />
            Generation failed
          </p>
          <p className="mt-1 line-clamp-3 text-red-200/80">
            {video.error_message || "Unknown error"}
          </p>
        </div>
      ) : null}

      <div className="mt-auto flex items-center justify-between gap-2 border-t border-line/60 pt-3">
        <span className="text-xs text-muted" title={formatDate(video.created_at)}>
          {timeAgo(video.created_at)}
        </span>
        <div className="flex items-center gap-2">
          {video.status === "completed" ? (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => onDownload?.(video)}
            >
              <Download className="h-3.5 w-3.5" />
              Download
            </button>
          ) : null}
          <button
            type="button"
            className="btn btn-danger btn-sm"
            onClick={() => onDelete?.(video)}
            aria-label={`Delete ${video.title}`}
            title="Delete video"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
          <Link href={`/videos/${video.id}`} className="btn btn-ghost btn-sm">
            View
            <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    </article>
  );
}
