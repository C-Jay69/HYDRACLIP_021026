"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ExternalLink,
  Loader2,
  Send,
  Wand2,
} from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { formatDate, platformLabel } from "@/lib/format";

export default function PublishingPage() {
  const { push } = useToast();
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setPosts(await api.published());
    } catch (err) {
      push(err?.message || "Could not load published posts.", "error");
    } finally {
      setLoading(false);
    }
  }, [push]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">
          Publishing
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-white">
          Published posts
        </h1>
        <p className="mt-1 text-sm text-muted">
          Everything HydraClip has published or exported from your schedules.
        </p>
      </header>

      {loading ? (
        <div className="card flex items-center justify-center gap-2 p-16 text-sm text-muted">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading published posts…
        </div>
      ) : posts.length === 0 ? (
        <EmptyState
          icon={Send}
          title="Nothing published yet"
          description="Create a schedule and publish a completed video to see it here."
          action={
            <Link href="/schedules" className="btn btn-primary btn-sm mt-1">
              <Wand2 className="h-4 w-4" />
              Go to schedules
            </Link>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {posts.map((post) => (
            <article key={post.id} className="card flex flex-col gap-3 p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="truncate text-sm font-semibold text-white">
                    {post.title || "Untitled post"}
                  </h2>
                  <p className="mt-1 text-xs text-muted">
                    {platformLabel(post.platform)} ·{" "}
                    {formatDate(post.published_at)}
                  </p>
                </div>
                <StatusBadge status={post.status} />
              </div>

              {post.error_message ? (
                <div className="flex items-start gap-2 rounded-xl border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-300">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>{post.error_message}</span>
                </div>
              ) : null}

              <div className="mt-auto flex items-center justify-between gap-2 border-t border-line/60 pt-3">
                <Link
                  href={`/videos/${post.video_id}`}
                  className="text-xs font-semibold text-muted transition hover:text-white"
                >
                  View source video
                </Link>
                {post.platform_url ? (
                  <a
                    href={post.platform_url}
                    target="_blank"
                    rel="noreferrer"
                    className="btn btn-ghost btn-sm"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                    Open post
                  </a>
                ) : (
                  <span className="text-xs text-muted">No public URL</span>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
