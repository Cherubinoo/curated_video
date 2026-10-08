import { notFound } from "next/navigation";
import { backend, BackendError } from "@/lib/backend";
import { RenderJobListResponse, Video } from "@/types";
import VideoDetailClient from "./VideoDetailClient";

export const dynamic = "force-dynamic";

export default async function VideoDetailPage({ params }: { params: { id: string } }) {
  let video: Video;
  try {
    video = await backend.get<Video>(`/videos/${params.id}`);
  } catch (err) {
    if (err instanceof BackendError && err.status === 404) {
      notFound();
    }
    throw err;
  }

  const jobs = await backend.get<RenderJobListResponse>(`/jobs?video_id=${params.id}&limit=1`);
  const latestJob = jobs.items[0] ?? null;

  return <VideoDetailClient initialVideo={video} initialJob={latestJob} />;
}
