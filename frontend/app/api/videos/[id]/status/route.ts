import { NextRequest, NextResponse } from "next/server";
import { backend, BackendError } from "@/lib/backend";
import { VideoStatusResponse } from "@/types";

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  try {
    const data = await backend.get<VideoStatusResponse>(`/videos/${params.id}/status`);
    return NextResponse.json(data);
  } catch (err) {
    if (err instanceof BackendError) {
      return NextResponse.json({ detail: err.detail }, { status: err.status });
    }
    return NextResponse.json({ detail: "Unexpected error" }, { status: 500 });
  }
}
