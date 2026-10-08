import Link from "next/link";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: "📊" },
  { href: "/videos", label: "Videos", icon: "🎬" },
  { href: "/videos/new", label: "New Video", icon: "➕" },
  { href: "/jobs", label: "Render Jobs", icon: "⚙️" },
];

export default function Sidebar() {
  return (
    <aside className="w-60 shrink-0 border-r border-border bg-panel px-4 py-6 flex flex-col gap-1">
      <div className="px-2 pb-6">
        <div className="text-lg font-semibold text-white">DSA Video Studio</div>
        <div className="text-xs text-gray-400">Educational animation platform</div>
      </div>
      {NAV_ITEMS.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-gray-300 hover:bg-surface hover:text-white transition-colors"
        >
          <span>{item.icon}</span>
          <span>{item.label}</span>
        </Link>
      ))}
    </aside>
  );
}
