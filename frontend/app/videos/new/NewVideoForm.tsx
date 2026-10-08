"use client";

import { useState, useTransition } from "react";
import { useFormState, useFormStatus } from "react-dom";
import { CreateVideoState, createAndGenerateVideo, expandPrompt } from "@/app/actions";
import { DSA_TOPICS } from "@/lib/topics";

const initialCreateState: CreateVideoState = { error: null };

function SubmitButton({ disabled }: { disabled: boolean }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending || disabled}
      className="w-full rounded-md bg-accent px-5 py-3 text-sm font-semibold text-white hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {pending ? "Generating video..." : "Generate Video"}
    </button>
  );
}

export default function NewVideoForm() {
  const [topic, setTopic] = useState("");
  const [description, setDescription] = useState("");
  const [prompt, setPrompt] = useState("");
  const [expandError, setExpandError] = useState<string | null>(null);
  const [isExpanding, startExpanding] = useTransition();
  const [showAdvanced, setShowAdvanced] = useState(false);
  // Server-side failures (e.g. a validation error creating the video) come
  // back here instead of throwing - an uncaught throw from a Server Action
  // crashes the whole page to Next.js's generic "Application error" screen
  // rather than showing something the admin can act on. A real observed
  // case: a very detailed description exceeded the backend's length limit.
  const [createState, createAction] = useFormState(createAndGenerateVideo, initialCreateState);

  const canSubmit = topic.trim().length > 0 && description.trim().length > 0;
  const canExpand = canSubmit && !isExpanding;

  const handlePreviewPrompt = () => {
    if (!canExpand) return;
    setExpandError(null);
    startExpanding(async () => {
      try {
        const expanded = await expandPrompt(topic, description);
        setPrompt(expanded);
        setShowAdvanced(true);
      } catch {
        setExpandError("Could not generate a preview. It will still be generated automatically when you submit.");
      }
    });
  };

  return (
    <form action={createAction} className="space-y-5">
      {createState.error && (
        <div className="rounded-md border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-200">
          {createState.error}
        </div>
      )}

      <div>
        <label className="mb-1 block text-sm font-medium text-gray-300" htmlFor="topic">
          Topic
        </label>
        <input
          id="topic"
          name="topic"
          type="text"
          required
          maxLength={255}
          list="topic-suggestions"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="e.g. Sliding Window, Binary Search, Trie..."
          className="w-full rounded-md border border-border bg-panel px-3 py-2.5 text-sm text-white placeholder:text-gray-500 focus:border-accent focus:outline-none"
        />
        <datalist id="topic-suggestions">
          {DSA_TOPICS.map((t) => (
            <option key={t} value={t} />
          ))}
        </datalist>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-gray-300" htmlFor="description">
          Description
        </label>
        <textarea
          id="description"
          name="description"
          required
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          placeholder="What should this video explain? e.g. 'How the sliding window technique avoids recomputing sums for subarray problems, with a walkthrough example.'"
          className="w-full rounded-md border border-border bg-panel px-3 py-2.5 text-sm text-white placeholder:text-gray-500 focus:border-accent focus:outline-none"
        />
      </div>

      <SubmitButton disabled={!canSubmit} />
      <p className="text-center text-xs text-gray-500">
        Generates a full narrated, animated explanation of the topic above via AWS Bedrock + Amazon
        Polly. Takes a bit longer than a placeholder demo - it&apos;s actually writing and rendering
        the explanation.
      </p>

      <details
        className="rounded-md border border-border bg-panel/50 p-3"
        open={showAdvanced}
        onToggle={(e) => setShowAdvanced((e.target as HTMLDetailsElement).open)}
      >
        <summary className="cursor-pointer text-sm font-medium text-gray-300">
          Advanced options (title, duration, difficulty, prompt preview)
        </summary>

        <div className="mt-4 space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-300" htmlFor="title">
              Title
            </label>
            <input
              id="title"
              name="title"
              maxLength={255}
              placeholder={topic || "Defaults to the topic if left blank"}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-white placeholder:text-gray-500 focus:border-accent focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-300" htmlFor="duration">
                Duration target (seconds, up to 10 min)
              </label>
              <input
                id="duration"
                name="duration"
                type="number"
                min={30}
                max={600}
                defaultValue={90}
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-white focus:border-accent focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-300" htmlFor="difficulty">
                Difficulty
              </label>
              <select
                id="difficulty"
                name="difficulty"
                defaultValue="beginner"
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-white focus:border-accent focus:outline-none"
              >
                <option value="beginner">Beginner</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
              </select>
            </div>
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between">
              <label className="block text-sm font-medium text-gray-300" htmlFor="prompt">
                Detailed prompt (optional preview)
              </label>
              <button
                type="button"
                onClick={handlePreviewPrompt}
                disabled={!canExpand}
                className="text-xs font-medium text-accent hover:underline disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isExpanding ? "Generating..." : "Preview generated prompt"}
              </button>
            </div>
            <p className="mb-2 text-xs text-gray-500">
              Leave blank to auto-generate from the topic + description above at submit time, or
              preview/edit it here first.
            </p>
            <textarea
              id="prompt"
              name="prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={6}
              placeholder="Auto-generated at submit time unless you preview/edit one here..."
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-white placeholder:text-gray-500 focus:border-accent focus:outline-none"
            />
            {expandError && <p className="mt-2 text-xs text-red-400">{expandError}</p>}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-300" htmlFor="notes">
              Notes
            </label>
            <textarea
              id="notes"
              name="notes"
              rows={2}
              placeholder="Anything else worth recording about this video..."
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-white placeholder:text-gray-500 focus:border-accent focus:outline-none"
            />
          </div>
        </div>
      </details>
    </form>
  );
}
