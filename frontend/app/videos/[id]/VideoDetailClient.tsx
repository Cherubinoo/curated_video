"use client";

import { KeyboardEvent, useCallback, useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import StatusBadge from "@/components/StatusBadge";
import ProgressBar from "@/components/ProgressBar";
import DeleteVideoButton from "@/components/DeleteVideoButton";
import { formatDate, formatDuration } from "@/lib/format";
import { regenerateVideo, triggerGenerate } from "@/app/actions";
import { RenderJob, RenderJobListResponse, Video, VideoStatusResponse } from "@/types";

const ACTIVE_STATUSES = new Set(["QUEUED", "PROCESSING"]);
const POLL_INTERVAL_MS = 2000;

export default function VideoDetailClient({
  initialVideo,
  initialJob,
}: {
  initialVideo: Video;
  initialJob: RenderJob | null;
}) {
  const [video, setVideo] = useState(initialVideo);
  const [job, setJob] = useState(initialJob);
  const [suggestions, setSuggestions] = useState("");
  const [isPending, startTransition] = useTransition();
  const [isStarting, setIsStarting] = useState(false);
  const router = useRouter();
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const hasAutoStartedRef = useRef(false);

  // Explicit re-fetch of the full video record - more reliable than
  // router.refresh() for updating THIS component's state: React doesn't
  // re-run useState's initializer just because the Server Component parent
  // passed a new `initialVideo` prop after a refresh.
  const refetchVideo = useCallback(async () => {
    try {
      const res = await fetch(`/api/videos/${video.id}`, { cache: "no-store" });
      if (res.ok) setVideo(await res.json());
    } catch {
      // transient - the polling loop (if active) will catch up
    }
  }, [video.id]);

  const refetchLatestJob = useCallback(async () => {
    try {
      const res = await fetch(`/api/jobs?video_id=${video.id}&limit=1`, { cache: "no-store" });
      if (res.ok) {
        const jobs: RenderJobListResponse = await res.json();
        if (jobs.items[0]) setJob(jobs.items[0]);
      }
    } catch {
      // transient - the polling loop (if active) will catch up
    }
  }, [video.id]);

  // Auto-start generation the moment a freshly-created (DRAFT) video lands
  // on this page, instead of making the admin wait on a frozen button on
  // the New Video form with no feedback - full AI generation can take over
  // a minute, and this page already has the progress bar + live logs below.
  useEffect(() => {
    if (video.status !== "DRAFT" || hasAutoStartedRef.current) return;
    hasAutoStartedRef.current = true;
    setIsStarting(true);
    startTransition(async () => {
      try {
        await triggerGenerate(video.id);
      } catch {
        // Generation kickoff itself failed (rare - the backend already
        // falls back internally for AI failures). Refetch below will show
        // whatever state the video actually ended up in either way.
      } finally {
        setIsStarting(false);
        await refetchVideo();
        await refetchLatestJob();
      }
    });
  }, [video.status, video.id, refetchVideo, refetchLatestJob]);

  const poll = useCallback(async () => {
    try {
      const statusRes = await fetch(`/api/videos/${video.id}/status`, { cache: "no-store" });
      if (statusRes.ok) {
        const status: VideoStatusResponse = await statusRes.json();
        setVideo((prev) => (prev.status === status.status ? prev : { ...prev, status: status.status }));
        setJob((prev) => (prev ? { ...prev, progress: status.progress, stage: status.stage ?? prev.stage } : prev));
      }
      const jobsRes = await fetch(`/api/jobs?video_id=${video.id}&limit=1`, { cache: "no-store" });
      if (jobsRes.ok) {
        const jobs: RenderJobListResponse = await jobsRes.json();
        if (jobs.items[0]) setJob(jobs.items[0]);
      }
    } catch {
      // transient network error - the next tick will retry
    }
  }, [video.id]);

  useEffect(() => {
    if (!ACTIVE_STATUSES.has(video.status)) {
      return;
    }
    timerRef.current = setInterval(async () => {
      await poll();
    }, POLL_INTERVAL_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [video.status, poll]);

  // Once the job leaves an active status, do one full re-fetch to pick up
  // video_url/thumbnail_url/error_message, which the lightweight /status
  // endpoint polled above doesn't include.
  const prevStatusRef = useRef(video.status);
  useEffect(() => {
    if (prevStatusRef.current !== video.status && !ACTIVE_STATUSES.has(video.status)) {
      refetchVideo();
      router.refresh(); // also refresh /videos and /dashboard's cached lists
    }
    prevStatusRef.current = video.status;
  }, [video.status, router, refetchVideo]);

  const handleRegenerate = () => {
    startTransition(async () => {
      await regenerateVideo(video.id, suggestions);
      setSuggestions("");
      await refetchVideo();
      await refetchLatestJob();
      router.refresh();
    });
  };

  const canRegenerate = !isPending && !isStarting && video.status !== "DRAFT" && !ACTIVE_STATUSES.has(video.status);

  const handleSuggestionsKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter regenerates (chat-input style); Shift+Enter inserts a newline.
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canRegenerate) handleRegenerate();
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-white">{video.title}</h1>
          <p className="text-sm text-gray-400">
            {video.topic} &middot; {video.difficulty} &middot; target {formatDuration(video.duration)}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={video.status} />
          <DeleteVideoButton
            videoId={video.id}
            videoTitle={video.title}
            status={video.status}
            redirectTo="/videos"
            className="rounded-md border border-red-900 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-950/40 disabled:cursor-not-allowed disabled:opacity-40"
          />
        </div>
      </div>

      {(isStarting || video.status === "DRAFT") && (
        <div className="flex items-center gap-3 rounded-lg border border-border bg-panel p-4 text-sm text-gray-300">
          <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          <span>
            Starting generation - AWS Bedrock is writing the scenes and narration, then Manim renders
            and Polly voices it. This can take 1-2 minutes; progress will appear below automatically.
          </span>
        </div>
      )}

      {ACTIVE_STATUSES.has(video.status) && job && (
        <div className="rounded-lg border border-border bg-panel p-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="text-gray-300">Stage: {job.stage}</span>
            <span className="text-gray-400">{formatDate(job.created_at)}</span>
          </div>
          <ProgressBar progress={job.progress} />
        </div>
      )}

      {video.status === "FAILED" && job?.error_message && (
        <div className="rounded-lg border border-red-800 bg-red-950/40 p-4 text-sm text-red-200">
          <div className="mb-1 font-medium">Render failed</div>
          <div>{job.error_message}</div>
        </div>
      )}

      {video.status === "COMPLETED" && video.video_url && (
        <div className="space-y-2">
          <div className="overflow-hidden rounded-lg border border-border bg-black">
            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <video controls className="w-full" poster={video.thumbnail_url ?? undefined} src={video.video_url} />
          </div>
          <a
            href={`/api/videos/${video.id}/download`}
            className="inline-block rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-blue-600"
          >
            Download Video
          </a>
        </div>
      )}

      <div className="rounded-lg border border-border bg-panel p-4">
        <h2 className="mb-2 text-sm font-medium text-gray-300">Prompt</h2>
        <pre className="whitespace-pre-wrap break-words text-sm text-gray-200">{video.prompt}</pre>
      </div>

      {video.notes && (
        <div className="rounded-lg border border-border bg-panel p-4">
          <h2 className="mb-2 text-sm font-medium text-gray-300">Notes</h2>
          <p className="text-sm text-gray-200">{video.notes}</p>
        </div>
      )}

      {job && (
        <div className="rounded-lg border border-border bg-panel p-4">
          <h2 className="mb-2 text-sm font-medium text-gray-300">Render Logs</h2>
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs text-gray-400">
            {job.logs || "No logs yet."}
          </pre>
        </div>
      )}

      <div className="rounded-lg border border-border bg-panel p-4">
        <h2 className="mb-2 text-sm font-medium text-gray-300">Updates / suggestions</h2>
        <p className="mb-2 text-xs text-gray-500">
          Type any changes you want (tone, focus, title, pacing...) and press Enter to regenerate.
          Shift+Enter for a new line.
        </p>
        <textarea
          value={suggestions}
          onChange={(e) => setSuggestions(e.target.value)}
          onKeyDown={handleSuggestionsKeyDown}
          disabled={!canRegenerate}
          rows={3}
          placeholder="e.g. make the narration more concise, emphasize the pointer movement..."
          className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-white placeholder:text-gray-500 focus:border-accent focus:outline-none disabled:opacity-50"
        />
      </div>

      <div className="flex items-center gap-3 text-sm text-gray-400">
        <span>Created {formatDate(video.created_at)}</span>
        <button
          onClick={handleRegenerate}
          disabled={!canRegenerate}
          className="ml-auto rounded-md border border-border px-4 py-2 text-sm font-medium text-gray-200 hover:bg-surface disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isPending ? "Regenerating..." : "Regenerate"}
        </button>
      </div>
    </div>
  );
}
