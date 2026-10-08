export default function ProgressBar({ progress }: { progress: number }) {
  const clamped = Math.max(0, Math.min(100, progress));
  return (
    <div className="w-full">
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface border border-border">
        <div
          className="h-full rounded-full bg-accent transition-all duration-500"
          style={{ width: `${clamped}%` }}
        />
      </div>
      <div className="mt-1 text-xs text-gray-400">{clamped}%</div>
    </div>
  );
}
