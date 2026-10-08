# DSA Video Studio

A production-ready platform for turning a structured educational video
specification into a deterministic, programmatically-rendered DSA concept
video using **Manim Community Edition** + **FFmpeg**.

The full pipeline works end to end **with real, topic-driven content** -
verified live, not just described: pick a topic and write a description,
and AWS Bedrock generates a complete video specification (which scenes,
which elements, what happens step by step) *and* a full narration script
specific to that topic - not a generic placeholder - which is then
validated, rendered with Manim, voiced with Amazon Polly, and muxed into a
real MP4 (`ffprobe`-confirmed H.264 + AAC). A "Sliding Window" request
produces a sliding-window animation with real narration explaining the
technique; a "Binary Search" request produces a binary-search one. If
generation ever fails (bad output, no AI configured, network issue), it
falls back to a deterministic three-scene demo animation rather than
breaking - see [What's stubbed vs. real](#whats-stubbed-vs-real) below.

## Architecture

```
Browser
  -> Next.js (dashboard, forms, video player; Server Actions/Route Handlers proxy to the API)
  -> FastAPI (validates input, persists rows, enqueues jobs - never renders anything itself)
  -> PostgreSQL (videos, specifications, render jobs, assets)
  -> Redis (Celery broker/result backend)
  -> video-worker (Celery consumer, concurrency=1: one render at a time)
      -> VideoSpecification (validated Pydantic DSL, never raw AI-generated Python)
      -> animation_engine (component + action registries build a Manim Scene from the spec)
      -> Manim (isolated subprocess, hard timeout)
      -> FFmpeg (normalizes to H.264/AAC/1920x1080/30fps, thumbnail)
      -> StorageService (local disk today; S3/R2-ready interface)
  -> Frontend video player (polls status, then plays the finished MP4)
```

The browser never executes Manim, and the FastAPI request path never blocks
on a render - `POST /api/videos/{id}/generate` returns as soon as a
`RenderJob` is queued; the worker does the rest asynchronously.

### Why the AI layer can't run arbitrary Python

Prompt → **AI/Specification Generator** → **structured VideoSpecification
JSON** → **strict Pydantic validation** (unknown action/element types,
out-of-range indices, invalid pointer references, and malformed data are
all rejected) → **animation engine** (fixed, reviewed Python; it interprets
the JSON, it doesn't execute anything from it) → **Manim** (always an
isolated, timeout-bounded subprocess) → **FFmpeg** → **MP4**.

See `backend/app/schemas/specification/` for the DSL and
`backend/animation_engine/` for the engine that interprets it.

## Repository layout

```
backend/
  app/
    core/            settings, structured logging, API-key auth, rate limiting, Celery app
    models/          SQLAlchemy: User, Video, VideoSpecification, RenderJob, Asset
    schemas/         API DTOs (video.py, job.py, dashboard.py) + the VideoSpecification DSL
    api/routes/      videos, jobs, dashboard, health
    repositories/    thin DB query layer
    services/        video_service, job_service, storage/, ai/, audio/, subtitles/
    workers/tasks.py Celery task: the full render job lifecycle
  animation_engine/
    components/      one file per DSL element type -> Manim Mobjects
    actions/         one file per action group -> Manim Animations
    validators/      validate_specification(): the single trust boundary
    renderer/        ManimRenderer (subprocess), FFmpegService, the dynamic Scene
  manim_scenes/      the one Manim CLI entrypoint (dynamic_scene.py)
  alembic/           DB migrations
  tests/             pytest suite (see "Running tests" below)
frontend/
  app/               Next.js App Router pages, Server Actions, proxy Route Handlers
  components/, lib/, types/
worker/              Dockerfile + a plain-Python launcher for the render worker
docker-compose.yml
.env.example
```

## Running it locally

Requires Docker Desktop.

```bash
cp .env.example .env       # edit values if you want, defaults work for local dev
docker compose up --build
```

This starts `postgres`, `redis`, `backend` (runs Alembic migrations, then
serves the API on **http://localhost:8000**), `video-worker` (Celery,
`--concurrency=1`), and `frontend` (**http://localhost:3000**).

First-time database setup: the backend's Alembic migration is generated
from the SQLAlchemy models. If you've changed a model, generate a new
revision from inside the running container:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe the change"
docker compose exec backend alembic upgrade head
```

### Creating a test video

1. Open http://localhost:3000/videos/new
2. Type a free-text **Topic** (autocomplete suggests common DSA topics, but
   anything goes) and a one/two-sentence **Description**. That's the whole
   required form - title, duration, difficulty, and the detailed prompt are
   all optional, tucked under **Advanced options** with sane defaults
   (title defaults to the topic; the detailed prompt is auto-generated via
   Bedrock at submit time if you don't preview/edit one yourself).
3. Click **Generate Video**. Video creation itself is instant, so you land
   on the video detail page right away rather than waiting on a frozen
   button - the page then auto-starts generation itself and shows a
   "Starting generation..." spinner, followed by the live stage/progress
   bar and render logs as soon as the job is queued
   (`QUEUED -> VALIDATING -> GENERATING_ANIMATION -> RENDERING_MANIM ->
   PROCESSING_VIDEO -> UPLOADING -> COMPLETED`), then plays the MP4. Full
   AI generation (Bedrock spec + retries, Polly synthesis, Manim render)
   commonly takes 1-2 minutes; nothing on this page blocks or looks frozen
   while that happens.

Or drive the API directly:

```bash
curl -s -X POST http://localhost:8000/api/videos \
  -H "X-API-Key: dev-local-admin-key-change-me" -H "Content-Type: application/json" \
  -d '{"title":"Demo","topic":"platform-demo","prompt":"anything","duration":30}'
# -> {"id": "...", "status": "DRAFT"}

curl -s -X POST http://localhost:8000/api/videos/<id>/generate \
  -H "X-API-Key: dev-local-admin-key-change-me"

curl -s http://localhost:8000/api/videos/<id>/status \
  -H "X-API-Key: dev-local-admin-key-change-me"
```

### Where the MP4 lives

`./storage/videos/{video_id}/versions/{version}/{specification.json,
final.mp4, thumbnail.jpg}` on the host (bind-mounted into both `backend`
and `video-worker` at `/data/storage`). The backend serves it at
`http://localhost:8000/media/videos/{video_id}/versions/{version}/final.mp4`,
which is exactly the URL stored in `Video.video_url` and used by the
frontend's `<video>` player.

### AI narration, TTS, download, and regenerate-with-suggestions

- **Topic + description -> detailed prompt**: `POST /api/videos/expand-prompt`
  (`app/services/ai/prompt_expander.py`) turns a short topic + description
  from the New Video form into a detailed prompt via the same Bedrock model,
  shown in an editable textarea before the admin proceeds. Same fallback
  pattern as narration generation below - a deterministic template if no AI
  provider is configured or the call fails, never a blocked/broken form.
- **Full video generation**: if `BEDROCK_API_KEY` is set, `/generate` calls
  AWS Bedrock (`BEDROCK_MODEL_ID`, default `deepseek.v3.2` - a low-cost
  model; see `app/services/ai/bedrock_specification_generator.py`) and asks
  it for a *complete* topic-driven specification - which scenes, which
  elements (arrays, pointers, code panels, shapes, camera moves - see
  `app/services/ai/dsl_reference.py` for the exact DSL it's taught), and a
  full narration script - not just a caption slapped on a fixed demo. The
  call sets Bedrock's `response_format: {"type": "json_object"}` (Mantle
  gateway, live-verified supported), which makes the model's own decoding
  guarantee syntactically valid JSON - this eliminated the single biggest
  cause of falling back to the demo (malformed/truncated free-text output
  that no amount of retrying fixed). Its output is still **never trusted
  directly** even so: it always passes through the same
  `validate_specification()` boundary as every other spec, plus an explicit
  check that a real narration script came back at all (a response with
  valid `scenes` but empty/missing narration is treated as a failure too -
  a real observed bug was a technically-valid spec with no narration,
  silently producing a mute video). An invalid or mute result gets sent
  back to the model with the specific problem for up to two corrective
  retries (raised from one now that `json_object` mode removed the
  unfixable-JSON failure mode - remaining failures are genuine semantic
  issues, like a real observed case of the model using an ELEMENT type
  name, e.g. `"text"`/`"arrow"`, as an ACTION `"type"`, which the DSL
  reference now explicitly calls out as two separate vocabularies) before
  falling back to the deterministic array+pointer demo, which itself always
  carries real narration (never a silent fallback either). A render never
  fails just because generation had a bad day.
  Live-verified across many topics with real, topic-specific output each
  time (not the demo fallback): "Sliding Window" (6 scenes), "Binary
  Search" (6 scenes), "Merge Sort" (5-scene divide-and-conquer walkthrough,
  1200+ character narration), and "Hash Table Collisions" (6-scene chaining
  walkthrough) - each `ffprobe`-confirmed to have both video and audio
  streams, each genuinely different, driven by what was asked.
  Calls go through `app/services/ai/bedrock_client.py`, which uses
  Bedrock's **Mantle** OpenAI-compatible gateway
  (`bedrock-mantle.<region>.api.aws/v1/chat/completions`, plain bearer-token
  auth, no AWS SigV4) rather than the native `bedrock-runtime` Converse API -
  on the account this was built against, Converse returned
  `Operation not allowed` for every model in every region (a full
  account-level restriction, confirmed via AWS's own model-access-request
  API), while Mantle worked with the identical key. If your account has
  normal Bedrock model access, either path works; Mantle is just the one
  proven to work here, and it also means Polly/Bedrock now share the same
  "plain HTTPS, no request signing" shape.
- **Voice-over**: `app/services/audio/get_voice_provider_name()` picks the
  provider - **Amazon Polly** (`app/services/audio/polly.py`) when
  `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` are set (preferred: no
  per-account credit gate), else **ElevenLabs** when `ELEVENLABS_API_KEY` is
  set, else none. Default voice is `POLLY_ENGINE=generative` /
  `POLLY_VOICE_ID=Ruth` (`POLLY_REGION=us-east-1`) - Polly's newest,
  most natural-sounding engine, a real step up from the initial
  `neural`/`Joanna` default; the generative engine is only available in
  specific regions (live-verified: `us-east-1`/`us-west-2` work for this
  account, `ap-south-1` returns zero generative voices - check
  `describe_voices` for yours if you change the region). The worker
  synthesizes the narration script and FFmpeg muxes it into the final MP4.
  Verified for real end-to-end: a genuine Polly `synthesize_speech` call,
  muxed by the actual worker code path into a real rendered video,
  `ffprobe`-confirmed to contain both an H.264 video stream and an AAC audio
  stream. A synthesis failure (e.g. no quota, no network) logs and falls
  back gracefully to an animation-only video - it never fails the render.
  Polly's real API limit is ~3000 characters per request - a long narration
  script (expected now that duration can go up to 10 minutes) is split into
  sentence-boundary chunks, synthesized separately, and losslessly
  concatenated with ffmpeg's concat demuxer, never silently truncated.
- **Video length actually scales with the requested duration**: the target
  narration word count, minimum scene count, and the model's completion
  token budget (`app/services/ai/bedrock_specification_generator.py`) all
  scale with `duration_target` instead of being fixed - previously a
  5-10 minute request got the same ~200-word narration and 4-7 scenes as a
  90-second one. Calibrated against live usage: a 300s request needs ~13.5K
  completion tokens, a 600s request ~16K - both now get real headroom
  instead of getting cut off mid-JSON, and the HTTP timeout scales with the
  token budget too (a live-verified 600s request took ~260s - well past the
  180s default). Separately, the final FFmpeg mux used to hard-truncate
  whichever stream was shorter (`-shortest`) - since the model's scene
  pacing rarely matches the narration length exactly, this silently cut the
  narration off mid-sentence to match a shorter animation, which defeated
  the point of a longer script. It now pads the shorter stream to match the
  longer one instead (extends video by holding the last frame, or pads
  audio with silence) so neither is ever truncated. Live-verified: a 300s
  request produced 16 scenes/882 words/342s of narration, and the final MP4
  runs the full 342s with synced audio - `ffprobe`-confirmed.
  That padding fallback (holding the last frame) is a legitimate safety net
  for a few seconds of mismatch, but two real generated videos had their
  *animation* cover only 33-59% of the narration's length (e.g. 48s of real
  motion for 134.6s of narration) - the rest was a frozen screen, which
  reads as "broken", not just imperfect. Asking the model nicely for scene
  `duration` fields to sum near the target wasn't reliable enough on its
  own (that field isn't even enforced by the renderer - only actions'
  actual `duration`/`wait_after` values drive real playback time). This is
  now hard-enforced the same way as the other DSL constraints: each
  candidate's real actions are summed (not the unenforced scene `duration`
  label) and compared against the requested duration, and a spec covering
  less than 70% of it is rejected with specific feedback ("only ~48
  seconds of real animation, needs ~150") and retried. Live-verified: a
  300s-target "Maximum Subarray (Kadane's Algorithm)" request improved from
  the kind of 33-59% coverage seen before to 249s of real animation against
  311.6s of narration (80% coverage, 17 scenes) - visually confirmed
  overlap-free at multiple timestamps including the padded tail.
- **Narration is genuinely synced to each scene's actual rendered timing, not just estimated pacing**:
  narration used to be one flat script for the whole video, muxed as a
  single track with no per-scene timing anchor - even with the total
  length matching well, one scene's narration taking much longer or
  shorter to speak than that scene's own actions take to play would drift
  the audio out of sync with the video, compounding through every later
  scene ("video going somewhere, audio somewhere else" - a real reported
  symptom). This was fixed in two layers:
  1. *Generation-time*: narration is written PER SCENE (each `Scene` has
     its own `narration` field - see `app/schemas/specification/scene.py`)
     and validated - a scene's narration word count / 2.5 (≈150 wpm) must
     land within roughly 0.35x-1.8x of that scene's own action time, or
     it's rejected and retried with the specific scene named.
  2. *Render-time* (the real fix): `animation_engine/renderer/
     scene_builder.py` records each scene's EXACT rendered start/end time
     from Manim's own clock (`self.renderer.time`) into a scene timeline.
     `app/workers/tasks.py` then synthesizes each scene's own narration
     separately and `FFmpegService.assemble_synced_video()` extracts that
     scene's precise video window, pads whichever of {that clip, that
     scene's own audio} is shorter to match the other, and concatenates
     every scene's matched pair in order - so a scene's narration is
     physically muxed to play only during that scene, regardless of how
     good the generation-time pacing estimate was. Falls back to the
     single-track path (`finalize()`) if no scene has its own narration or
     if the sync step itself fails - a render must never fail because a
     newer code path hit a problem.
  Live-verified twice: video/audio durations matched within 0.05s end to
  end (e.g. 32.267s video vs 32.312s audio), confirmed via `ffprobe` and
  by extracting frames at specific timestamps to confirm the right scene's
  content plays at the right time.
  Separately, a live timeout during this work surfaced a related gap: a
  single slow/failed Bedrock call used to fall back to the generic demo
  immediately, discarding the rest of the retry budget over what was often
  just transient slowness - a failed call is now retried like any other
  recoverable failure instead of giving up on the first one.
- **Every topic must cover a fixed 17-point curriculum**: what it is, why
  it's needed, intuition, mechanism, rules/invariants, a visual example,
  step-by-step execution, why it works, variations, pseudocode, a Python
  implementation, common problem patterns, recognition signals, common
  mistakes, time/space complexity, and a closing mental model (see
  `_SYSTEM_PROMPT`'s "MANDATORY CONTENT OUTLINE" in
  `bedrock_specification_generator.py`) - a direct product requirement, not
  just "cover the topic well". Scene/word-count floors were raised
  accordingly (minimum 10 scenes, 280 words, 9000 completion tokens,
  regardless of how short the requested duration is) since properly
  touching all 17 points needs real content even at a short duration.
  Conceptual points that don't have an obvious animation (rules, mistakes,
  recognition signals) get explicit guidance on giving each sub-point its
  own sequential reveal so their action time naturally matches their
  narration, rather than one static screen. Live-verified: a "Binary
  Search" request produced 15 real scenes mapping cleanly onto the
  outline (definition, rules+example, step-by-step, why-it-works,
  pseudocode split across 2 scenes, Python implementation split across 3,
  problem patterns, common mistakes, complexity, outro).
- **Layout discipline**: `app/services/ai/dsl_reference.py` gives the model
  four fixed, gap-free vertical zones (title/content-upper/content-lower/
  caption, each with an exact center y to default to) and text-length
  limits to stop elements overlapping or overflowing, and `Coordinate.x`/
  `.y` are hard-bounded (`[-6.5,6.5]`/`[-3.6,3.6]`, just inside the true
  1920x1080 frame edge) at the schema level - an out-of-frame coordinate
  fails validation outright rather than silently rendering off-screen. The
  same reference also explicitly forbids `null` for `array.values` entries
  and `update_text.new_text` - a real failure mode seen in practice
  (Pydantic correctly rejects a `null`, but it used to burn the whole retry
  budget before the model reliably self-corrected).
  Two further overlap bugs were found in real generated videos and fixed at
  the schema level (not just prompt wording, which the model doesn't always
  follow): (1) `code_block` had no cap on line count, and an 11-line block
  at the default font_size rendered ~5.5 units tall - nearly the whole
  frame - guaranteeing it overlapped everything else on screen; height and
  width are now hard-capped (`app/schemas/specification/elements.py`),
  calibrated against real measurements of the actual renderer (DejaVu Sans
  Mono, live-measured line height/width, not guessed). (2) `paragraph`'s
  `line_width` field was defined in the schema but silently ignored by
  `animation_engine/components/text.py` - any paragraph longer than a few
  words rendered as one unbroken line running off both edges of the frame.
  Word-wrapping is now actually implemented (calibrated the same way), and
  a paragraph long enough to still overflow its zone after wrapping is
  rejected the same way an oversized code_block is. Live-verified: a real
  112-character paragraph that previously ran off both edges of the frame
  now wraps cleanly into 3 lines fully inside the frame.
- **Story + concept, not just one**: the system prompt requires every
  generated video to work as both a narrative (concrete problem -> step by
  step build-up -> payoff -> why it matters) and an accurate technical
  explanation using the actual numbers/code on screen - flashy motion with
  no real teaching, or an accurate but static/boring video, are both
  treated as failures in the prompt itself, not just checked after the fact.
- **Duration target has no artificial cap beyond the schema's**: the New
  Video form's duration field allows up to 600 seconds (10 minutes) rather
  than the earlier 150-second UI cap, matching what the backend schema
  already allowed - the render timeout (`RENDER_TIMEOUT_SECONDS`) is a
  separate, unrelated safety limit on how long a single Manim subprocess
  may run.
- **Regenerate with suggestions**: the video detail page has an "Updates /
  suggestions" box - type feedback and press Enter (Shift+Enter for a
  newline) to regenerate. This calls `POST /api/videos/{id}/regenerate`
  with `{"suggestions": "..."}`, which folds that text into the prompt sent
  to the specification generator and records it on `Video.notes`, then
  creates a new specification version and render job.
- **Download**: once a video is `COMPLETED`, the detail page shows a
  **Download Video** button (`GET /api/videos/{id}/download`, proxied
  through the frontend) that streams the file with a proper
  `Content-Disposition: attachment` header and a slugified filename, so the
  browser saves it locally instead of just playing it inline.
- **Branded outro on every video**: `app/services/ai/branding.py` appends a
  fixed, hand-authored "Code2Day Learning / A product of Tera2Nano" end
  card (with its own short narration) to every specification right before
  final validation - both the real Bedrock-generated path and the
  demo-shell fallback. This is deterministic, reviewed content, not
  something the model is asked to remember to include, so it's never
  missing regardless of what the model produces. Live-verified: the card
  renders cleanly with no overlap, and the branding line is spoken as part
  of the final narration track.

**Setting these up**: copy your keys into `.env` (never commit them - the
file is gitignored) as `BEDROCK_API_KEY`/`BEDROCK_MANTLE_REGION`/
`BEDROCK_MODEL_ID`, and `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/
`POLLY_REGION`/`POLLY_VOICE_ID` for Polly, then
`docker compose up -d --force-recreate backend video-worker`. These are two
**separate** kinds of credentials: a Bedrock API key is a bearer token that
only authorizes Bedrock/Bedrock Runtime calls and cannot call Polly; Polly
needs a real IAM access key/secret (standard AWS SigV4). If your account
has normal Bedrock model access but Mantle doesn't work for you, switch
`bedrock_client.py` back to the native `bedrock-runtime` Converse API (the
authentication and DSL-prompt logic are identical either way - only the
transport changes).

### Running tests

All 136 tests (135 fast + the real end-to-end Manim render) run inside
`video-worker` - it's the only image with Manim/FFmpeg/pytest all
installed (the API `backend` image deliberately does not have Manim):

```bash
docker compose exec video-worker pytest -v              # everything
docker compose exec video-worker pytest -m "not e2e" -v # fast only (~13s, no real render)
docker compose exec video-worker pytest -m e2e -v       # just the real Manim/FFmpeg render
```

Verified in this repository: all 136 pass, including a real Manim render
producing an H.264/1920x1080/30fps MP4 (confirmed with `ffprobe`).

## What's stubbed vs. real

| Layer | Status |
|---|---|
| Frontend, API, DB models, job queue, Docker | Real, production-shaped |
| VideoSpecification DSL + validation | Real - full schema, strict rejection rules |
| Animation engine: Text/Title/Subtitle/Paragraph/Label, Rectangle/Circle/Line/Arrow, Array, Pointer, CodeBlock | Real Manim renderers |
| Animation engine: Graph, Tree, Stack, Queue, LinkedList, DPTable, HashMap | Schema-complete; renderer raises a clear "not implemented yet" (see `animation_engine/components/base.py:UnimplementedComponent`) |
| `VideoSpecificationGenerator` (prompt -> spec) | `BedrockSpecificationGenerator` when `BEDROCK_API_KEY` is set - real, topic-driven scenes/elements/actions/narration from AWS Bedrock (validated, with a corrective retry), live-verified for multiple topics; falls back to `PlaceholderSpecGenerator`'s deterministic demo on any Bedrock/validation failure |
| `AudioService` | `PollyAudioService` when AWS credentials are set, else `ElevenLabsAudioService` when `ELEVENLABS_API_KEY` is set (real TTS, muxed into the final MP4 - both verified live); falls back to `NoOpAudioService` (animation-only) otherwise or on any synthesis error |
| `SubtitleService` | No-op implementation; every video renders without subtitles today |
| `StorageService` | `LocalStorageService` is real; `S3StorageService`/`R2StorageService` are structural stubs (interface-complete, `NotImplementedError` body) |
| Auth | Single static admin API key (`X-API-Key`), sufficient for an internal single-admin tool; `User` model exists for a real login system later |

## Plugging in the pieces that come next

**A real educational prompt driving real scenes.** Already real -
`BedrockSpecificationGenerator` generates the full scenes/elements/actions
and narration from whatever topic + description you give it (see the AI
section above), not just narration text over a fixed shell. Extending it
further (richer element types once Graph/Tree/etc. get real renderers, more
scenes for longer videos, few-shot examples per topic category) is tuning
`app/services/ai/dsl_reference.py`'s prompt - no API, worker, or frontend
changes needed.

**Voice/TTS.** Already real via `PollyAudioService`/`ElevenLabsAudioService`
- see the section above. A different provider is another `AudioService`
subclass (`app/services/audio/`) swapped into `get_audio_service()`;
`FFmpegService.finalize()` already accepts an `audio_path` and mixes it in
when present.

**Subtitles.** Same pattern: implement a `SubtitleService`
(`app/services/subtitles/`) that returns an `.srt`/`.vtt` (e.g. via
Whisper), swap it into `get_subtitle_service()`.

**The other 17 DSA visualizations** (Graph, Tree, Heap, Topological Sort,
Union-Find, DP tables, Trie, bit manipulation, ...). The DSL already has
schema-complete element types for the DSA-primitive ones (Graph, Tree,
Stack, Queue, LinkedList, DPTable, HashMap - see
`app/schemas/specification/elements.py`). Adding real visuals for one is:
write a `SceneComponent` in `animation_engine/components/`, register it in
`animation_engine/components/registry.py`, and (if it needs new verbs) add
action executors in `animation_engine/actions/` the same way. Nothing else
in the API/DB/worker/validation layers needs to change.

**S3/R2 storage.** Implement the bodies of `S3StorageService`/
`R2StorageService` in `app/services/storage/` (interface + a docstring
sketch are already there), set `STORAGE_TYPE=s3` (or `r2`) in `.env`.

## Security notes

- The admin API key never reaches the browser: the frontend's Server
  Components/Actions/Route Handlers call FastAPI server-side; client-side
  code only ever calls same-origin Next.js routes.
- Every storage path is sanitized (`app/services/storage/path_utils.py`)
  against traversal before touching disk.
- Manim always runs as an isolated subprocess with a hard timeout
  (`RENDER_TIMEOUT_SECONDS`); the worker container runs as a non-root user.
- Unhandled exceptions never leak stack traces to API clients - full
  tracebacks go to structured server logs only (`app/main.py`).
- `VideoSpecification` uses `extra="forbid"` everywhere: unknown fields,
  unknown element/action types, and out-of-range references are rejected
  before anything ever reaches the animation engine.
#   c u r a t e d _ v i d e o  
 