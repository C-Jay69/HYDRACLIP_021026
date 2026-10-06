/**
 * Projects workspace: create projects, start generation jobs, follow them to
 * a finished render.
 *
 * Talks to the backend through the same-origin ``/api`` proxy (src/lib/api).
 * Generation is asynchronous by design: POST returns 202 with a job id, this
 * page polls GET /jobs/{id} until it reaches a terminal status, then offers
 * the preview link from GET /videos/{id}/media.
 */

import { SignedOutGuard, WorkspaceNav } from "@/components/WorkspaceNav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthSession } from "@/auth-session";
import { api, listAll } from "@/lib/api";
import {
  AlertTriangle,
  CheckCircle2,
  Clapperboard,
  FolderOpen,
  Loader2,
  PlayCircle,
  Plus,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

type ProjectSummary = {
  id: number;
  title: string;
  topic: string | null;
  status: string;
  video_count?: number;
  created_at?: string | null;
};

type VideoSummary = {
  id: number;
  project_id: number;
  status: string;
  script_text: string | null;
  error_message: string | null;
  duration_seconds: number | null;
  created_at?: string | null;
};

type JobSummary = {
  id: number;
  video_id: number;
  status: string;
  progress_pct: number;
  error_message: string | null;
};

type StageInfo = {
  name: string;
  description: string;
  available: boolean;
  reason: string | null;
};

type PipelineStatus = {
  stages: StageInfo[];
  default_stages: string[];
  media_storage?: { public_urls: boolean; backend: string } | null;
};

const POLL_MS = 4000;
const STAGE_LABELS: Record<string, string> = {
  script: "Script",
  voiceover: "Voiceover",
  assemble: "Render video",
};

export function ProjectsPage() {
  const session = useAuthSession();
  const signedIn = session.status === "authenticated";

  const [projects, setProjects] = useState<ProjectSummary[] | "loading" | "unavailable">(
    "loading",
  );
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [openProject, setOpenProject] = useState<ProjectSummary | null>(null);
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [job, setJob] = useState<JobSummary | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const loadProjects = useCallback(() => {
    void (async () => {
      try {
        setProjects(await listAll<ProjectSummary>("/projects"));
      } catch {
        setProjects("unavailable");
      }
    })();
  }, []);

  useEffect(() => {
    if (!signedIn) return;
    loadProjects();
    void (async () => {
      try {
        setPipeline(await api<PipelineStatus>("/pipeline/status"));
      } catch {
        setPipeline(null);
      }
    })();
  }, [signedIn, loadProjects]);

  // Stop any poll loop when the page unmounts.
  useEffect(
    () => () => {
      if (pollRef.current !== null) window.clearInterval(pollRef.current);
    },
    [],
  );

  if (!signedIn) return <SignedOutGuard page="Projects" />;

  async function createProject(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const created = await api<ProjectSummary>("/projects", {
        method: "POST",
        body: JSON.stringify({ title: title.trim(), topic: topic.trim() || null }),
      });
      setTitle("");
      setTopic("");
      setProjects((current) => (Array.isArray(current) ? [created, ...current] : current));
      setOpenProject(created);
      setVideos([]);
      setJob(null);
      setPreviewUrl(null);
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Could not create the project.");
    } finally {
      setCreating(false);
    }
  }

  async function openDetails(project: ProjectSummary) {
    setOpenProject(project);
    setJob(null);
    setJobError(null);
    setPreviewUrl(null);
    try {
      setVideos(await listAll<VideoSummary>(`/projects/${project.id}/videos`));
    } catch {
      setVideos([]);
    }
  }

  async function startGeneration(stages: string[]) {
    if (!openProject || stages.length === 0) return;
    setStarting(true);
    setJobError(null);
    setPreviewUrl(null);
    try {
      const accepted = await api<{ job: JobSummary; video: VideoSummary }>(
        `/projects/${openProject.id}/generate`,
        { method: "POST", body: JSON.stringify({ stages }) },
      );
      setJob(accepted.job);
      pollJob(accepted.job.id);
    } catch (error) {
      setJobError(error instanceof Error ? error.message : "Generation could not start.");
    } finally {
      setStarting(false);
    }
  }

  function pollJob(jobId: number) {
    if (pollRef.current !== null) window.clearInterval(pollRef.current);
    pollRef.current = window.setInterval(() => {
      void (async () => {
        try {
          const current = await api<JobSummary>(`/jobs/${jobId}`);
          setJob(current);
          if (!["pending", "running"].includes(current.status)) {
            if (pollRef.current !== null) window.clearInterval(pollRef.current);
            pollRef.current = null;
            if (current.status === "completed") await showPreview(current.video_id);
            loadProjects();
          }
        } catch {
          // transient network error: keep polling
        }
      })();
    }, POLL_MS);
  }

  async function showPreview(videoId: number) {
    try {
      const media = await api<{ url: string | null; reason?: string }>(
        `/videos/${videoId}/media`,
      );
      if (!media.url) {
        setJobError(media.reason ?? "The render finished but no preview URL is available.");
      }
      setPreviewUrl(media.url);
      if (openProject) {
        setVideos(await listAll<VideoSummary>(`/projects/${openProject.id}/videos`));
      }
    } catch {
      setJobError("Could not load the finished video.");
    }
  }

  const availableStages = (pipeline?.stages ?? []).filter((stage) => stage.available);
  const defaultStages = pipeline?.default_stages ?? ["script"];

  return (
    <main className="min-h-screen bg-background">
      <WorkspaceNav active="/projects" />
      <div className="mx-auto max-w-7xl space-y-10 px-6 py-10">
        <section aria-labelledby="projects-heading">
          <div className="flex items-center gap-2.5">
            <FolderOpen className="size-5 text-brand-bright" aria-hidden="true" />
            <h1 id="projects-heading" className="text-2xl font-bold tracking-tight">
              Projects
            </h1>
          </div>

          <form
            onSubmit={(event) => void createProject(event)}
            className="mt-5 flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 sm:flex-row sm:items-end"
          >
            <div className="flex-1 space-y-1.5">
              <Label htmlFor="project-title">What is this video about?</Label>
              <Input
                id="project-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="e.g. 5 habits of calm people"
                maxLength={200}
                required
              />
            </div>
            <div className="flex-[2] space-y-1.5">
              <Label htmlFor="project-topic">Topic / notes (optional)</Label>
              <Input
                id="project-topic"
                value={topic}
                onChange={(event) => setTopic(event.target.value)}
                placeholder="Angles, audience, tone…"
                maxLength={2000}
              />
            </div>
            <Button type="submit" disabled={creating || !title.trim()}>
              {creating ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
              New project
            </Button>
          </form>
          {createError && (
            <p
              role="alert"
              className="mt-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm"
            >
              {createError}
            </p>
          )}

          {projects === "loading" ? (
            <p className="mt-4 flex items-center gap-2 text-sm text-muted-foreground" role="status">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Loading projects…
            </p>
          ) : projects === "unavailable" ? (
            <p className="mt-4 rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
              The HydraClip API is unreachable right now. Refresh to retry.
            </p>
          ) : projects.length === 0 ? (
            <p className="mt-4 rounded-lg border border-dashed border-border bg-card/60 p-6 text-sm text-muted-foreground">
              No projects yet. Create your first one above, then generate a script or a full
              video for it.
            </p>
          ) : (
            <ul className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {projects.map((project) => (
                <li key={project.id}>
                  <button
                    type="button"
                    onClick={() => void openDetails(project)}
                    aria-pressed={openProject?.id === project.id}
                    className={
                      openProject?.id === project.id
                        ? "w-full rounded-xl border border-ring bg-card p-4 text-left shadow-sm"
                        : "w-full rounded-xl border border-border bg-card p-4 text-left shadow-sm transition-colors hover:border-ring/60"
                    }
                  >
                    <p className="truncate font-medium">{project.title}</p>
                    <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                      {project.topic || "No topic notes"}
                    </p>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {project.status}
                      {typeof project.video_count === "number" &&
                        ` · ${project.video_count} video(s)`}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {openProject && (
          <section
            aria-labelledby="generate-heading"
            className="rounded-2xl border border-border bg-card p-5"
          >
            <div className="flex items-center gap-2.5">
              <Clapperboard className="size-5 text-brand-bright" aria-hidden="true" />
              <h2 id="generate-heading" className="text-lg font-bold">
                Generate for “{openProject.title}”
              </h2>
            </div>

            {pipeline && availableStages.length === 0 && (
              <p className="mt-3 flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
                <AlertTriangle className="size-4 text-amber-500" aria-hidden="true" />
                No pipeline stages are available on this deployment right now (missing API
                keys or tooling).
              </p>
            )}

            <div className="mt-4 flex flex-wrap gap-2">
              {availableStages.length > 0 && (
                <Button onClick={() => void startGeneration(defaultStages)} disabled={starting}>
                  {starting ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <PlayCircle className="size-4" />
                  )}
                  Generate {defaultStages.map((s) => STAGE_LABELS[s] ?? s).join(" + ")}
                </Button>
              )}
              {availableStages
                .filter((stage) => !defaultStages.includes(stage.name))
                .map((stage) => (
                  <Button
                    key={stage.name}
                    variant="outline"
                    disabled={starting}
                    onClick={() => void startGeneration([stage.name])}
                  >
                    {STAGE_LABELS[stage.name] ?? stage.name} only
                  </Button>
                ))}
            </div>

            {jobError && (
              <p
                role="alert"
                className="mt-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm"
              >
                {jobError}
              </p>
            )}

            {job && (
              <div className="mt-4 rounded-xl border border-border p-4" role="status">
                <p className="flex items-center gap-2 text-sm font-medium">
                  {job.status === "completed" ? (
                    <CheckCircle2 className="size-4 text-emerald-500" aria-hidden="true" />
                  ) : job.status === "failed" || job.status === "cancelled" ? (
                    <XCircle className="size-4 text-destructive" aria-hidden="true" />
                  ) : (
                    <Loader2
                      className="size-4 animate-spin text-brand-bright"
                      aria-hidden="true"
                    />
                  )}
                  Job #{job.id} — {job.status} ({job.progress_pct}%)
                </p>
                {job.error_message && (
                  <p className="mt-2 text-sm text-muted-foreground">{job.error_message}</p>
                )}
              </div>
            )}

            {previewUrl && (
              <div className="mt-4">
                <h3 className="text-sm font-semibold">Preview</h3>
                <video
                  controls
                  src={previewUrl}
                  className="mt-2 w-full max-w-sm rounded-xl border border-border"
                />
              </div>
            )}

            {videos.length > 0 && (
              <div className="mt-5">
                <h3 className="text-sm font-semibold">Videos in this project</h3>
                <ul className="mt-2 space-y-2">
                  {videos.map((video) => (
                    <li key={video.id} className="rounded-lg border border-border p-3 text-sm">
                      <span className="font-medium">Video #{video.id}</span> — {video.status}
                      {video.error_message && (
                        <span className="block text-xs text-destructive">
                          {video.error_message}
                        </span>
                      )}
                      {video.script_text && (
                        <span className="mt-1 block line-clamp-2 text-xs text-muted-foreground">
                          {video.script_text}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
