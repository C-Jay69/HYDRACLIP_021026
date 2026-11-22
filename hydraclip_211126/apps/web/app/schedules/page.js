"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CalendarClock,
  ExternalLink,
  Loader2,
  Play,
  Send,
  Wand2,
} from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import {
  formatDate,
  platformLabel,
  toLocalDateTimeInput,
} from "@/lib/format";

const platforms = ["youtube", "instagram", "tiktok", "x"];

export default function SchedulesPage() {
  const { push } = useToast();

  const [schedules, setSchedules] = useState([]);
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState("");
  const [lastResult, setLastResult] = useState(null);

  const [videoId, setVideoId] = useState("");
  const [platform, setPlatform] = useState("youtube");
  const [when, setWhen] = useState(() =>
    toLocalDateTimeInput(new Date(Date.now() + 60 * 60 * 1000)),
  );

  const completedVideos = useMemo(
    () => videos.filter((video) => video.status === "completed"),
    [videos],
  );

  const load = useCallback(
    async (showSpinner = false) => {
      if (showSpinner) setLoading(true);
      try {
        const [scheduleList, videoList] = await Promise.all([
          api.schedules(),
          api.videos(),
        ]);
        setSchedules(scheduleList);
        setVideos(videoList);
      } catch (err) {
        push(err?.message || "Could not load schedules.", "error");
      } finally {
        setLoading(false);
      }
    },
    [push],
  );

  useEffect(() => {
    load(true);
  }, [load]);

  useEffect(() => {
    if (!videoId && completedVideos.length > 0) {
      setVideoId(completedVideos[0].id);
    }
  }, [completedVideos, videoId]);

  async function handleCreate(event) {
    event.preventDefault();
    if (!videoId) {
      push("Choose a completed video first.", "warning");
      return;
    }
    if (!when) {
      push("Choose a date and time.", "warning");
      return;
    }

    setSubmitting(true);
    try {
      await api.createSchedule({
        video_id: videoId,
        platform,
        scheduled_at: new Date(when).toISOString(),
        timezone:
          Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      });
      push("Schedule created.", "success");
      await load(false);
    } catch (err) {
      push(err?.message || "Could not create the schedule.", "error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handlePublish(schedule) {
    setBusyId(schedule.id);
    setLastResult(null);
    try {
      const result = await api.publishNow(schedule.id);
      if (result?.platform_url) {
        setLastResult({
          message: `Published to ${platformLabel(schedule.platform)}.`,
          url: result.platform_url,
        });
        push(`Published to ${platformLabel(schedule.platform)}.`, "success");
      } else {
        setLastResult({
          message: `Manual upload required for ${platformLabel(
            schedule.platform,
          )}. Check the Publishing page for the export.`,
          url: null,
        });
        push("Manual upload required. See Publishing.", "info");
      }
      await load(false);
    } catch (err) {
      push(err?.message || "Could not publish this schedule.", "error");
    } finally {
      setBusyId("");
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">
          Schedules
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-white">
          Plan your publishing
        </h1>
        <p className="mt-1 text-sm text-muted">
          Pick a finished video, choose a platform, and publish now or schedule it
          for later.
        </p>
      </header>

      {lastResult ? (
        <div className="flex flex-col items-start justify-between gap-2 rounded-xl border border-accent/20 bg-accent/10 p-3 text-sm text-accent sm:flex-row sm:items-center">
          <span>{lastResult.message}</span>
          {lastResult.url ? (
            <a
              href={lastResult.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-semibold underline underline-offset-2"
            >
              Open post
              <ExternalLink className="h-3 w-3" />
            </a>
          ) : null}
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)]">
        <section className="card h-fit p-5 lg:sticky lg:top-6">
          <div className="flex items-start gap-3">
            <span className="rounded-xl border border-accent2/20 bg-accent2/10 p-2 text-accent2">
              <CalendarClock className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-lg font-semibold text-white">New schedule</h2>
              <p className="mt-0.5 text-sm text-muted">
                Only completed videos can be scheduled.
              </p>
            </div>
          </div>

          {completedVideos.length === 0 && !loading ? (
            <EmptyState
              icon={Wand2}
              title="No completed videos"
              description="Generate and finish a video first, then come back to schedule it."
              action={
                <Link href="/#generate" className="btn btn-primary btn-sm mt-1">
                  Generate a video
                </Link>
              }
            />
          ) : (
            <form onSubmit={handleCreate} className="mt-5 space-y-4">
              <div>
                <label className="label" htmlFor="schedule-video">
                  Video
                </label>
                <select
                  id="schedule-video"
                  className="input"
                  value={videoId}
                  onChange={(event) => setVideoId(event.target.value)}
                >
                  {completedVideos.map((video) => (
                    <option key={video.id} value={video.id}>
                      {video.title}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="label" htmlFor="schedule-platform">
                  Platform
                </label>
                <select
                  id="schedule-platform"
                  className="input"
                  value={platform}
                  onChange={(event) => setPlatform(event.target.value)}
                >
                  {platforms.map((item) => (
                    <option key={item} value={item}>
                      {platformLabel(item)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="label" htmlFor="schedule-when">
                  Date & time
                </label>
                <input
                  id="schedule-when"
                  type="datetime-local"
                  className="input"
                  value={when}
                  onChange={(event) => setWhen(event.target.value)}
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary w-full"
                disabled={submitting || !videoId}
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <CalendarClock className="h-4 w-4" />
                )}
                {submitting ? "Creating…" : "Create schedule"}
              </button>
            </form>
          )}

          <p className="mt-4 text-xs leading-relaxed text-muted">
            YouTube uses your connected account. Instagram, TikTok and X produce a
            manual export package for now.
          </p>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Upcoming & past</h2>
            <span className="badge border-line bg-panel2/70 text-slate-300">
              {schedules.length} total
            </span>
          </div>

          {loading ? (
            <div className="card flex items-center justify-center gap-2 p-16 text-sm text-muted">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading schedules…
            </div>
          ) : schedules.length === 0 ? (
            <EmptyState
              icon={CalendarClock}
              title="Nothing scheduled"
              description="Create a schedule to queue a video for publishing."
            />
          ) : (
            <div className="space-y-3">
              {schedules.map((schedule) => {
                const video = videos.find(
                  (item) => item.id === schedule.video_id,
                );
                return (
                  <article
                    key={schedule.id}
                    className="card flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="truncate text-sm font-semibold text-white">
                          {video?.title || "Video"}
                        </h3>
                        <StatusBadge status={schedule.status} />
                      </div>
                      <p className="mt-1 text-xs text-muted">
                        {platformLabel(schedule.platform)} ·{" "}
                        {formatDate(schedule.scheduled_at)} · {schedule.timezone}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <Link
                        href={`/videos/${schedule.video_id}`}
                        className="btn btn-ghost btn-sm"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                        Video
                      </Link>
                      {schedule.status === "pending" ? (
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() => handlePublish(schedule)}
                          disabled={busyId === schedule.id}
                        >
                          {busyId === schedule.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Play className="h-3.5 w-3.5" />
                          )}
                          Publish now
                        </button>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs text-muted">
                          <Send className="h-3.5 w-3.5" />
                          {schedule.status}
                        </span>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
