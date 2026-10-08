import Link from "next/link";
import { backend } from "@/lib/backend";
import { RenderJobListResponse } from "@/types";
import StatusBadge from "@/components/StatusBadge";
import { formatDate } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function JobsPage() {
  const data = await backend.get<RenderJobListResponse>("/jobs?limit=100");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Render Jobs</h1>
        <p className="text-sm text-gray-400">{data.total} total</p>
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-panel text-left text-gray-400">
            <tr>
              <th className="px-4 py-2 font-medium">Job</th>
              <th className="px-4 py-2 font-medium">Video</th>
              <th className="px-4 py-2 font-medium">Stage</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Progress</th>
              <th className="px-4 py-2 font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {data.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-gray-500">
                  No render jobs yet.
                </td>
              </tr>
            )}
            {data.items.map((j) => (
              <tr key={j.id} className="border-t border-border hover:bg-panel/60">
                <td className="px-4 py-2 font-mono text-xs text-gray-300">{j.id.slice(0, 8)}</td>
                <td className="px-4 py-2">
                  <Link href={`/videos/${j.video_id}`} className="text-accent hover:underline">
                    {j.video_id.slice(0, 8)}
                  </Link>
                </td>
                <td className="px-4 py-2 text-gray-300">{j.stage}</td>
                <td className="px-4 py-2">
                  <StatusBadge status={j.status} />
                </td>
                <td className="px-4 py-2 text-gray-400">{j.progress}%</td>
                <td className="px-4 py-2 text-gray-400">{formatDate(j.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
