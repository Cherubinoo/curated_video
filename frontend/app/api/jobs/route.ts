import { NextRequest, NextResponse } from "next/server";
import { backend, BackendError } from "@/lib/backend";
import { RenderJobListResponse } from "@/types";

export async function GET(req: NextRequest) {
  const search = req.nextUrl.search; // forwards ?video_id=...&limit=...
  try {
    const data = await backend.get<RenderJobListResponse>(`/jobs${search}`);
    return NextResponse.json(data);
  } catch (err) {
    if (err instanceof BackendError) {
      return NextResponse.json({ detail: err.detail }, { status: err.status });
    }
    return NextResponse.json({ detail: "Unexpected error" }, { status: 500 });
  }
}
