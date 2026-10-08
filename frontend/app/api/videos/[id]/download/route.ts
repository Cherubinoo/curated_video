import { NextRequest, NextResponse } from "next/server";

const BACKEND_INTERNAL_URL = process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";
const API_KEY = process.env.API_KEY || "";

// Streams the backend's attachment response straight through, so the
// browser gets the same Content-Disposition/filename without the API key
// ever reaching client-side JS.
export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  const res = await fetch(`${BACKEND_INTERNAL_URL}/api/videos/${params.id}/download`, {
    headers: { "X-API-Key": API_KEY },
    cache: "no-store",
  });

  if (!res.ok || !res.body) {
    return NextResponse.json({ detail: "Video not available for download" }, { status: res.status || 404 });
  }

  const headers = new Headers();
  const contentType = res.headers.get("content-type");
  const contentDisposition = res.headers.get("content-disposition");
  if (contentType) headers.set("content-type", contentType);
  if (contentDisposition) headers.set("content-disposition", contentDisposition);

  return new NextResponse(res.body, { status: 200, headers });
}
