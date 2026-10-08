const COLORS: Record<string, string> = {
  DRAFT: "bg-gray-700 text-gray-200",
  QUEUED: "bg-blue-900 text-blue-200",
  PROCESSING: "bg-amber-900 text-amber-200",
  RUNNING: "bg-amber-900 text-amber-200",
  PENDING: "bg-blue-900 text-blue-200",
  COMPLETED: "bg-emerald-900 text-emerald-200",
  FAILED: "bg-red-900 text-red-200",
};

export default function StatusBadge({ status }: { status: string }) {
  const classes = COLORS[status] ?? "bg-gray-700 text-gray-200";
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${classes}`}>
      {status}
    </span>
  );
}
