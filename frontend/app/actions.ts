"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { backend, BackendError } from "@/lib/backend";
import { PromptExpandResponse, VideoCreateResponse } from "@/types";

export interface CreateVideoState {
  error: string | null;
}

/** FastAPI 422 responses put a list of `{msg, loc, ...}` objects in
 * `detail`, not a string - a real observed crash logged that raw array
 * straight to the console (readable there, but useless as a user-facing
 * message) and, worse, let the underlying BackendError propagate
 * uncaught out of the Server Action, which Next.js turns into a generic
 * "Application error: a server-side exception has occurred" page instead
 * of a helpful inline message. */
function formatBackendErrorDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((issue) => {
        if (issue && typeof issue === "object" && "msg" in issue) {
          const loc = Array.isArray((issue as { loc?: unknown[] }).loc)
            ? (issue as { loc: unknown[] }).loc.filter((p) => p !== "body").join(".")
            : undefined;
          return loc ? `${loc}: ${(issue as { msg: string }).msg}` : String((issue as { msg: string }).msg);
        }
        return JSON.stringify(issue);
      })
      .join("; ");
  }
  return JSON.stringify(detail);
}

export async function createAndGenerateVideo(
  _prevState: CreateVideoState,
  formData: FormData
): Promise<CreateVideoState> {
  const topic = String(formData.get("topic") || "").trim();
  const description = String(formData.get("description") || "").trim();
  let title = String(formData.get("title") || "").trim();
  let prompt = String(formData.get("prompt") || "").trim();
  const notes = String(formData.get("notes") || "").trim();
  const duration = Number(formData.get("duration") || 90);
  const difficulty = String(formData.get("difficulty") || "beginner");

  if (!topic || !description) {
    return { error: "Topic and description are required." };
  }
  if (!title) {
    title = topic;
  }
  if (!prompt) {
    try {
      prompt = await expandPrompt(topic, description);
    } catch (err) {
      // Bedrock/network hiccup generating the detailed prompt - fall back
      // to the raw description rather than blocking video creation on it.
      if (err instanceof BackendError) {
        console.error("expand-prompt failed during create, using description as-is", err.detail);
      }
      prompt = description;
    }
  }

  let created: VideoCreateResponse;
  try {
    created = await backend.post<VideoCreateResponse>("/videos", {
      title,
      topic,
      prompt,
      duration,
      difficulty,
      notes: notes || null,
    });
  } catch (err) {
    if (err instanceof BackendError) {
      return { error: formatBackendErrorDetail(err.detail) };
    }
    return { error: "Could not create the video - please try again." };
  }

  // Deliberately NOT calling /generate here - full AI generation can take
  // over a minute (Bedrock spec generation + retry + Polly + Manim), and
  // blocking this redirect on it would leave the admin staring at a static
  // "Generating..." button with zero feedback for that whole time. Instead
  // redirect immediately (this is fast: just the DB insert above) and let
  // the video detail page kick off /generate itself on mount, where the
  // existing progress bar + live log polling can actually show what's
  // happening - see VideoDetailClient's auto-start effect.
  revalidatePath("/videos");
  revalidatePath("/dashboard");
  // `redirect()` works by throwing a special internal error that Next.js
  // catches further up the tree - letting it propagate here (rather than
  // wrapping it in another try/catch) is required, not a bug.
  redirect(`/videos/${created.id}`);
}

export async function expandPrompt(topic: string, description: string): Promise<string> {
  const trimmedTopic = topic.trim();
  const trimmedDescription = description.trim();
  if (!trimmedTopic || !trimmedDescription) {
    throw new Error("Topic and description are required to generate a prompt.");
  }
  const result = await backend.post<PromptExpandResponse>("/videos/expand-prompt", {
    topic: trimmedTopic,
    description: trimmedDescription,
  });
  return result.prompt;
}

export async function triggerGenerate(videoId: string): Promise<void> {
  // Separated from createAndGenerateVideo so the video detail page can kick
  // this off itself right after the (fast) create+redirect, with the page's
  // own progress bar/log polling visible for the whole - potentially
  // minutes-long - generation, instead of the admin watching a frozen button.
  await backend.post(`/videos/${videoId}/generate`);
  revalidatePath(`/videos/${videoId}`);
  revalidatePath("/jobs");
}

export async function regenerateVideo(videoId: string, suggestions?: string): Promise<void> {
  const trimmed = suggestions?.trim();
  await backend.post(`/videos/${videoId}/regenerate`, trimmed ? { suggestions: trimmed } : {});
  revalidatePath(`/videos/${videoId}`);
  revalidatePath("/jobs");
}

export async function deleteVideo(videoId: string): Promise<void> {
  await backend.delete(`/videos/${videoId}`);
  revalidatePath("/videos");
  revalidatePath("/dashboard");
  revalidatePath("/jobs");
}
