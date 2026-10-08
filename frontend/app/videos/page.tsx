import Link from "next/link";
import { backend } from "@/lib/backend";
import { VideoListResponse } from "@/types";
import StatusBadge from "@/components/StatusBadge";
import DeleteVideoButton from "@/components/DeleteVideoButton";
import { formatDate, formatDuration } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function VideosPage() {
  const data = await backend.get<VideoListResponse>("/videos?limit=100");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Videos</h1>
          <p className="text-sm text-gray-400">{data.total} total</p>
        </div>
        <Link
          href="/videos/new"
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-blue-600"
        >
          + New Video
        </Link>
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-panel text-left text-gray-400">
            <tr>
              <th className="px-4 py-2 font-medium">Title</th>
              <th className="px-4 py-2 font-medium">Topic</th>
              <th className="px-4 py-2 font-medium">Difficulty</th>
              <th className="px-4 py-2 font-medium">Duration</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Created</th>
              <th className="px-4 py-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-gray-500">
                  No videos yet.{" "}
                  <Link href="/videos/new" className="text-accent hover:underline">
                    Create one
                  </Link>
                  .
                </td>
              </tr>
            )}
            {data.items.map((v) => (
              <tr key={v.id} className="border-t border-border hover:bg-panel/60">
                <td className="px-4 py-2">
                  <Link href={`/videos/${v.id}`} className="text-accent hover:underline">
                    {v.title}
                  </Link>
                </td>
                <td className="px-4 py-2 text-gray-300">{v.topic}</td>
                <td className="px-4 py-2 text-gray-300">{v.difficulty}</td>
                <td className="px-4 py-2 text-gray-300">{formatDuration(v.duration)}</td>
                <td className="px-4 py-2">
                  <StatusBadge status={v.status} />
                </td>
                <td className="px-4 py-2 text-gray-400">{formatDate(v.created_at)}</td>
                <td className="px-4 py-2">
                  <DeleteVideoButton videoId={v.id} videoTitle={v.title} status={v.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
