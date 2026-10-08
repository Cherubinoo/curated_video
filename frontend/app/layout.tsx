import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "DSA Video Studio",
  description: "Deterministic, programmable educational DSA animation video platform.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-surface text-gray-100">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 px-8 py-8 max-w-6xl">{children}</main>
        </div>
      </body>
    </html>
  );
}
