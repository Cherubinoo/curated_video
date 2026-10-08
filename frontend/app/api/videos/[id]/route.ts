import { NextRequest, NextResponse } from "next/server";
import { backend, BackendError } from "@/lib/backend";
import { Video } from "@/types";

// Lets client components explicitly re-fetch the full video record (title,
// prompt, video_url, thumbnail_url, error-relevant fields) after a status
// transition, rather than relying on a Server Component prop refresh to
// reach an already-mounted Client Component's local state - React does not
// re-run useState's initializer on new props, so that path is unreliable
// for updating client-held state after router.refresh().
export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  try {
    const data = await backend.get<Video>(`/videos/${params.id}`);
    return NextResponse.json(data);
  } catch (err) {
    if (err instanceof BackendError) {
      return NextResponse.json({ detail: err.detail }, { status: err.status });
    }
    return NextResponse.json({ detail: "Unexpected error" }, { status: 500 });
  }
}
