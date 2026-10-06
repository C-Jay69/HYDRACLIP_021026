/**
 * Scheduling: queue a completed video for publishing and review what went out.
 *
 * Only platforms with a connected account can be scheduled (the backend
 * rejects the rest); the publish itself runs on the worker at the chosen
 * time — this page creates and monitors the schedule rows.
 */

import { SignedOutGuard, WorkspaceNav } from "@/components/WorkspaceNav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuthSession } from "@/auth-session";
import { api, listAll } from "@/lib/api";
import { CalendarClock, Loader2, Send, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

type ScheduleRow = {
  id: number;
  video_id: number;
  platform: string;
  scheduled_at: string;
  status: string;
  platform_url: string | null;
};

type PublishedRow = {
  id: number;
  video_id: number;
  platform: string;
  platform_url: string | null;
  status: string;
  published_at: string | null;
  error_message: string | null;
};

type CompletedVideo = { id: number; project_id: number; status: string };
type ConnectedAccount = { id: number; platform: string; account_name: string };

export function SchedulePage() {
  const session = useAuthSession();
  const signedIn = session.status === "authenticated";

  const [schedules, setSchedules] = useState<ScheduleRow[] | "loading">("loading");
  const [posts, setPosts] = useState<PublishedRow[]>([]);
  const [videos, setVideos] = useState<CompletedVideo[]>([]);
  const [accounts, setAccounts] = useState<ConnectedAccount[]>([]);
  const [videoId, setVideoId] = useState("");
  const [platform, setPlatform] = useState("");
  const [when, setWhen] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!signedIn) return;
    void (async () => {
      try {
        setSchedules(await listAll<ScheduleRow>("/schedules"));
        setPosts(await listAll<PublishedRow>("/published-posts"));
        setVideos(await listAll<CompletedVideo>("/videos"));
        setAccounts(await listAll<ConnectedAccount>("/social/accounts"));
      } catch {
        setSchedules([]);
      }
    })();
  }, [signedIn]);

  if (!signedIn) return <SignedOutGuard page="Schedule" />;

  async function createSchedule(event: React.FormEvent) {
    event.preventDefault();
    if (!videoId || !platform || !when) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api<ScheduleRow>("/schedules", {
        method: "POST",
        body: JSON.stringify({
          video_id: Number(videoId),
          platform,
          // datetime-local carries no zone; toISOString yields UTC, which is
          // the format the backend stores and the worker compares against.
          scheduled_at: new Date(when).toISOString(),
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        }),
      });
      setSchedules((current) => (Array.isArray(current) ? [created, ...current] : current));
      setVideoId("");
      setWhen("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not schedule the post.");
    } finally {
      setBusy(false);
    }
  }

  async function cancelSchedule(id: number) {
    try {
      await api(`/schedules/${id}`, { method: "DELETE" });
      setSchedules((current) =>
        Array.isArray(current) ? current.filter((row) => row.id !== id) : current,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not cancel the schedule.");
    }
  }

  const upcoming = Array.isArray(schedules) ? schedules : [];
  const completed = videos.filter((v) => v.status === "completed" || v.status === "ready");
  const platforms = accounts.length > 0 ? Array.from(new Set(accounts.map((a) => a.platform))) : [];

  function formatWhen(iso: string): string {
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  }

  return (
    <main className="min-h-screen bg-background">
      <WorkspaceNav active="/schedule" />
      <div className="mx-auto max-w-7xl space-y-10 px-6 py-10">
        <section aria-labelledby="schedule-heading">
          <div className="flex items-center gap-2.5">
            <CalendarClock className="size-5 text-brand-bright" aria-hidden="true" />
            <h1 id="schedule-heading" className="text-2xl font-bold tracking-tight">
              Schedule
            </h1>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Queue a finished video for publishing, or review what already went out.
          </p>

          {/* Create schedule form */}
          <form
            onSubmit={(event) => void createSchedule(event)}
            className="mt-5 grid gap-3 rounded-2xl border border-border bg-card p-5 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end"
          >
            <div className="space-y-1.5">
              <Label htmlFor="sched-video">Video</Label>
              <Select value={videoId} onValueChange={setVideoId}>
                <SelectTrigger id="sched-video" className="w-full">
                  <SelectValue placeholder="Pick a finished video" />
                </SelectTrigger>
                <SelectContent>
                  {completed.length === 0 ? (
                    <SelectItem value="_none" disabled>
                      No finished videos yet
                    </SelectItem>
                  ) : (
                    completed.map((video) => (
                      <SelectItem key={video.id} value={String(video.id)}>
                        Video #{video.id} (project {video.project_id})
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="sched-platform">Platform</Label>
              <Select value={platform} onValueChange={setPlatform}>
                <SelectTrigger id="sched-platform" className="w-full">
                  <SelectValue placeholder="Choose platform" />
                </SelectTrigger>
                <SelectContent>
                  {platforms.length === 0 ? (
                    <>
                      <SelectItem value="youtube">YouTube</SelectItem>
                      <SelectItem value="instagram">Instagram</SelectItem>
                      <SelectItem value="tiktok">TikTok</SelectItem>
                      <SelectItem value="x">X</SelectItem>
                    </>
                  ) : (
                    platforms.map((p) => (
                      <SelectItem key={p} value={p}>
                        {p.charAt(0).toUpperCase() + p.slice(1)}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="sched-when">Publish at</Label>
              <Input
                id="sched-when"
                type="datetime-local"
                value={when}
                onChange={(event) => setWhen(event.target.value)}
                required
              />
            </div>

            <Button type="submit" disabled={busy || !videoId || !platform || !when}>
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
              Schedule
            </Button>
          </form>

          {platforms.length === 0 && (
            <p className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
              No social accounts are connected yet — head to{" "}
              <a className="underline" href="/connect">
                /connect
              </a>{" "}
              to link YouTube (auto-publish) or grab the manual-upload fallback for the others.
            </p>
          )}

          {error && (
            <p
              role="alert"
              className="mt-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm"
            >
              {error}
            </p>
          )}
        </section>

        {/* Upcoming scheduled posts */}
        <section aria-labelledby="schedule-upcoming">
          <h2 id="schedule-upcoming" className="text-lg font-bold">
            Upcoming posts ({upcoming.length})
          </h2>
          {upcoming.length === 0 ? (
            <p className="mt-3 rounded-lg border border-dashed border-border bg-card/60 p-6 text-sm text-muted-foreground">
              Nothing scheduled yet. Use the form above to queue your first post.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {upcoming.map((row) => (
                <li
                  key={row.id}
                  className="flex items-center justify-between gap-3 rounded-xl border border-border bg-card p-4 text-sm"
                >
                  <div>
                    <p className="font-medium">
                      Video #{row.video_id} → {row.platform}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {formatWhen(row.scheduled_at)} · {row.status}
                    </p>
                    {row.platform_url && (
                      <a
                        href={row.platform_url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-1 inline-block text-xs text-brand-bright underline"
                      >
                        View on {row.platform}
                      </a>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void cancelSchedule(row.id)}
                    disabled={busy}
                  >
                    <Trash2 className="size-4" />
                    Cancel
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Already published */}
        <section aria-labelledby="schedule-published">
          <h2 id="schedule-published" className="text-lg font-bold">
            Published ({posts.length})
          </h2>
          {posts.length === 0 ? (
            <p className="mt-3 rounded-lg border border-dashed border-border bg-card/60 p-6 text-sm text-muted-foreground">
              No posts have been published yet. Once a scheduled post ships you’ll see it here with
              its live link.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {posts.map((post) => (
                <li
                  key={post.id}
                  className="rounded-xl border border-border bg-card p-4 text-sm"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium">
                      Video #{post.video_id} → {post.platform}
                    </p>
                    <span
                      className={
                        post.status === "published"
                          ? "rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-medium text-emerald-500"
                          : "rounded-full bg-amber-500/15 px-2.5 py-0.5 text-xs font-medium text-amber-500"
                      }
                    >
                      {post.status}
                    </span>
                  </div>
                  {post.published_at && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Published {formatWhen(post.published_at)}
                    </p>
                  )}
                  {post.error_message && (
                    <p className="mt-1 text-xs text-destructive">{post.error_message}</p>
                  )}
                  {post.platform_url && (
                    <a
                      href={post.platform_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 inline-block text-xs text-brand-bright underline"
                    >
                      View post
                    </a>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
