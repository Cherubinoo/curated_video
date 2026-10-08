"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { deleteVideo } from "@/app/actions";

const ACTIVE_STATUSES = new Set(["QUEUED", "PROCESSING"]);

export default function DeleteVideoButton({
  videoId,
  videoTitle,
  status,
  redirectTo,
  className,
}: {
  videoId: string;
  videoTitle: string;
  status: string;
  /** Where to navigate after a successful delete. Omit to just refresh the current page (list views). */
  redirectTo?: string;
  className?: string;
}) {
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const isActive = ACTIVE_STATUSES.has(status);

  const handleDelete = () => {
    if (isActive || isPending) return;
    const confirmed = window.confirm(
      `Delete "${videoTitle}"? This permanently removes the video, its render history, and any stored files.`
    );
    if (!confirmed) return;

    setError(null);
    startTransition(async () => {
      try {
        await deleteVideo(videoId);
        if (redirectTo) {
          router.push(redirectTo);
        } else {
          router.refresh();
        }
      } catch {
        setError("Delete failed.");
      }
    });
  };

  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={handleDelete}
        disabled={isPending || isActive}
        title={isActive ? "Cannot delete while queued/processing" : "Delete this video"}
        className={
          className ??
          "text-xs font-medium text-red-400 hover:text-red-300 disabled:cursor-not-allowed disabled:opacity-40"
        }
      >
        {isPending ? "Deleting..." : "Delete"}
      </button>
      {error && <span className="text-xs text-red-400">{error}</span>}
    </span>
  );
}
