import Link from "next/link";
import { backend } from "@/lib/backend";
import { DashboardResponse } from "@/types";
import StatCard from "@/components/StatCard";
import StatusBadge from "@/components/StatusBadge";
import DeleteVideoButton from "@/components/DeleteVideoButton";
import { formatDate } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const data = await backend.get<DashboardResponse>("/dashboard");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-white">Dashboard</h1>
        <p className="text-sm text-gray-400">Overview of your DSA video pipeline.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard label="Total" value={data.stats.total} />
        <StatCard label="Draft" value={data.stats.draft} />
        <StatCard label="Queued" value={data.stats.queued} />
        <StatCard label="Processing" value={data.stats.processing} />
        <StatCard label="Completed" value={data.stats.completed} />
        <StatCard label="Failed" value={data.stats.failed} />
      </div>

      <section>
        <h2 className="mb-3 text-lg font-medium text-white">Recent Videos</h2>
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-panel text-left text-gray-400">
              <tr>
                <th className="px-4 py-2 font-medium">Title</th>
                <th className="px-4 py-2 font-medium">Topic</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Created</th>
                <th className="px-4 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_videos.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-gray-500">
                    No videos yet.{" "}
                    <Link href="/videos/new" className="text-accent hover:underline">
                      Create one
                    </Link>
                    .
                  </td>
                </tr>
              )}
              {data.recent_videos.map((v) => (
                <tr key={v.id} className="border-t border-border hover:bg-panel/60">
                  <td className="px-4 py-2">
                    <Link href={`/videos/${v.id}`} className="text-accent hover:underline">
                      {v.title}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-gray-300">{v.topic}</td>
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
      </section>

      <section>
        <h2 className="mb-3 text-lg font-medium text-white">Recent Render Jobs</h2>
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-panel text-left text-gray-400">
              <tr>
                <th className="px-4 py-2 font-medium">Job</th>
                <th className="px-4 py-2 font-medium">Stage</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Progress</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_jobs.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-gray-500">
                    No render jobs yet.
                  </td>
                </tr>
              )}
              {data.recent_jobs.map((j) => (
                <tr key={j.id} className="border-t border-border hover:bg-panel/60">
                  <td className="px-4 py-2 font-mono text-xs text-gray-300">{j.id.slice(0, 8)}</td>
                  <td className="px-4 py-2 text-gray-300">{j.stage}</td>
                  <td className="px-4 py-2">
                    <StatusBadge status={j.status} />
                  </td>
                  <td className="px-4 py-2 text-gray-400">{j.progress}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
