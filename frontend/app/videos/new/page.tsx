import NewVideoForm from "./NewVideoForm";

export default function NewVideoPage() {
  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">New Video</h1>
        <p className="text-sm text-gray-400">
          Pick a topic and write a short description, then click{" "}
          <strong className="text-gray-300">Generate Detailed Prompt</strong> to turn that into a
          detailed video prompt you can review and edit. The animation itself still renders the
          platform&apos;s bundled demo (array + pointer) today, so you can verify the full pipeline
          end to end - the generated narration/title come from the prompt above when an AI provider
          is configured.
        </p>
      </div>
      <NewVideoForm />
    </div>
  );
}
