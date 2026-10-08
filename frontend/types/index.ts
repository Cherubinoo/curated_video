// Mirrors backend/app/schemas/{video,job,dashboard}.py response shapes.

export type VideoStatus = "DRAFT" | "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";
export type Difficulty = "beginner" | "intermediate" | "advanced";
export type RenderJobStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
export type RenderStage =
  | "QUEUED"
  | "VALIDATING"
  | "GENERATING_ANIMATION"
  | "RENDERING_MANIM"
  | "PROCESSING_VIDEO"
  | "UPLOADING"
  | "COMPLETED"
  | "FAILED";

export interface Video {
  id: string;
  title: string;
  topic: string;
  prompt: string;
  notes: string | null;
  status: VideoStatus;
  duration: number;
  difficulty: Difficulty;
  video_url: string | null;
  thumbnail_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface PromptExpandResponse {
  prompt: string;
}

export interface VideoListResponse {
  items: Video[];
  total: number;
}

export interface VideoCreateResponse {
  id: string;
  status: VideoStatus;
}

export interface VideoStatusResponse {
  status: VideoStatus;
  progress: number;
  stage: RenderStage | null;
}

export interface RenderJob {
  id: string;
  video_id: string;
  specification_id: string | null;
  status: RenderJobStatus;
  progress: number;
  stage: RenderStage;
  logs: string;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface RenderJobListResponse {
  items: RenderJob[];
  total: number;
}

export interface DashboardStats {
  total: number;
  draft: number;
  queued: number;
  processing: number;
  completed: number;
  failed: number;
}

export interface DashboardResponse {
  stats: DashboardStats;
  recent_videos: Video[];
  recent_jobs: RenderJob[];
}
