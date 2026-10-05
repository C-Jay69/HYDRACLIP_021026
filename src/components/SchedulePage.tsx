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

  // __SCHEDULE_JSX__
}
