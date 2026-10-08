"""FFmpeg post-processing: normalizes whatever Manim produced into the
standard output contract (H.264/AAC/target resolution/target FPS) and
generates a thumbnail. Resolution/FPS are parameters, not hardcoded, so they
can later be driven from `spec.settings` for non-default canvases.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

# Every audio segment fed into `assemble_synced_video`'s concat step must
# share the exact same sample rate/channel layout - Amazon Polly's real
# output is 24000 Hz mono (matched here to avoid an unnecessary resample of
# the actual narration), and silence segments are generated to match.
_AUDIO_SAMPLE_RATE = 24000
_AUDIO_CHANNELS = 1


@dataclass
class SceneAudioSegment:
    """One scene's exact rendered video window (from
    ManimRenderResult.scene_timeline) paired with that same scene's own
    synthesized narration clip (or None if the scene has no narration) -
    the input to `FFmpegService.assemble_synced_video`."""

    scene_id: str
    start: float
    end: float
    audio_path: Path | None


class FFmpegError(Exception):
    def __init__(self, message: str, logs: str = ""):
        super().__init__(message)
        self.logs = logs


class FFmpegService:
    def __init__(self, timeout_seconds: int = 300):
        self.timeout_seconds = timeout_seconds

    def finalize(
        self,
        input_video: Path,
        output_path: Path,
        *,
        width: int,
        height: int,
        fps: int,
        audio_path: Path | None = None,
    ) -> str:
        """Re-encode to H.264/yuv420p at the target size/fps, muxing an audio
        track if one was provided.

        The animation's rendered length and the narration's spoken length
        rarely match exactly (the model's scene timing is a best-effort
        estimate, not exact). Whichever stream is SHORTER gets padded to
        match the longer one - the video by holding its final frame, the
        audio by appending silence - rather than the old `-shortest`
        behavior, which silently cut off the longer stream. That used to
        mean a longer narration script got truncated mid-sentence to match
        a shorter animation - a real observed bug, and the opposite of what
        a longer narration script is for.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        scale_pad_filter = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        )

        if audio_path is not None and audio_path.exists():
            cmd = self._build_muxed_command(
                input_video, audio_path, output_path, scale_pad_filter=scale_pad_filter, fps=fps
            )
        else:
            cmd = [
                "ffmpeg", "-y", "-i", str(input_video), "-an",
                "-vf", scale_pad_filter,
                "-r", str(fps),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(output_path),
            ]
        return self._run(cmd)

    def _build_muxed_command(
        self,
        input_video: Path,
        audio_path: Path,
        output_path: Path,
        *,
        scale_pad_filter: str,
        fps: int,
    ) -> list[str]:
        video_filter = scale_pad_filter
        audio_filter = "anull"
        try:
            video_duration = self._probe_duration(input_video)
            audio_duration = self._probe_duration(audio_path)
            pad_video = max(0.0, audio_duration - video_duration)
            pad_audio = max(0.0, video_duration - audio_duration)
            if pad_video > 0.05:
                video_filter += f",tpad=stop_mode=clone:stop_duration={pad_video:.3f}"
            if pad_audio > 0.05:
                audio_filter = f"apad=pad_dur={pad_audio:.3f}"
            logger.info(
                "ffmpeg_duration_match",
                video_duration=video_duration,
                audio_duration=audio_duration,
                pad_video=pad_video,
                pad_audio=pad_audio,
            )
        except Exception as exc:  # noqa: BLE001 - duration probing must never block the render
            logger.warning("ffmpeg_duration_probe_failed_using_shortest", error=str(exc))
            return [
                "ffmpeg", "-y",
                "-i", str(input_video),
                "-i", str(audio_path),
                "-c:a", "aac", "-shortest",
                "-vf", scale_pad_filter,
                "-r", str(fps),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(output_path),
            ]

        return [
            "ffmpeg", "-y",
            "-i", str(input_video),
            "-i", str(audio_path),
            "-filter_complex", f"[0:v]{video_filter}[v];[1:a]{audio_filter}[a]",
            "-map", "[v]", "-map", "[a]",
            "-r", str(fps),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path),
        ]

    def assemble_synced_video(
        self,
        input_video: Path,
        output_path: Path,
        *,
        width: int,
        height: int,
        fps: int,
        segments: list[SceneAudioSegment],
        work_dir: Path,
    ) -> str:
        """Builds the final video from PER-SCENE video/audio pairs instead
        of one whole-video track - the real fix for narration drifting out
        of sync with the visuals over the course of a video (a scene's
        pacing estimate, however good, is still an estimate; this uses each
        scene's ACTUAL rendered duration, straight from Manim's own clock).

        For each scene: extract its exact video window (accurate re-encoded
        seek, not stream-copy - stream-copy trims can land on the wrong
        keyframe), then pad whichever of {that segment's video, that
        scene's own narration audio} is shorter to match the other (video by
        holding its last frame, audio by appending silence - a scene with no
        narration at all gets silence for its full video length, so the
        audio track stays continuous and every later scene's audio still
        lines up). Concatenating same-codec segments this way (as opposed to
        one big filter_complex trying to do everything at once - tried and
        abandoned; it silently dropped frames) is what the live-verified
        prototype behind this method actually was.
        """
        work_dir.mkdir(parents=True, exist_ok=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        scale_pad_filter = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        )
        prepared_video = work_dir / "prepared.mp4"
        self._run(
            [
                "ffmpeg", "-y", "-i", str(input_video), "-an",
                "-vf", scale_pad_filter,
                "-r", str(fps),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                str(prepared_video),
            ]
        )

        video_parts: list[Path] = []
        audio_parts: list[Path] = []
        for i, segment in enumerate(segments):
            video_duration = max(0.0, segment.end - segment.start)
            seg_video = work_dir / f"seg_v{i}.mp4"
            self._run(
                [
                    "ffmpeg", "-y",
                    "-i", str(prepared_video),
                    "-ss", f"{segment.start:.3f}",
                    "-to", f"{segment.end:.3f}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(seg_video),
                ]
            )

            audio_duration = (
                self._probe_duration(segment.audio_path)
                if segment.audio_path is not None and segment.audio_path.exists()
                else 0.0
            )
            pad_video = max(0.0, audio_duration - video_duration)
            pad_audio = max(0.0, video_duration - audio_duration)

            final_video = seg_video
            if pad_video > 0.05:
                final_video = work_dir / f"seg_v{i}_padded.mp4"
                self._run(
                    [
                        "ffmpeg", "-y", "-i", str(seg_video),
                        "-vf", f"tpad=stop_mode=clone:stop_duration={pad_video:.3f}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(final_video),
                    ]
                )
            video_parts.append(final_video)

            seg_audio = work_dir / f"seg_a{i}.m4a"
            if segment.audio_path is not None and segment.audio_path.exists():
                af = f"apad=pad_dur={pad_audio:.3f}" if pad_audio > 0.05 else "anull"
                # -ar/-ac force every segment (real narration AND silence
                # below) to the SAME sample rate/channel layout - Polly's
                # real output is 24000 Hz mono, which does not match
                # anullsrc's default. A real observed bug: concatenating
                # segments with mismatched audio formats via the concat
                # demuxer produced a badly corrupted duration (41.75s
                # reported for what should have been 22.7s of real audio).
                self._run(
                    [
                        "ffmpeg", "-y", "-i", str(segment.audio_path),
                        "-af", af, "-ar", str(_AUDIO_SAMPLE_RATE), "-ac", str(_AUDIO_CHANNELS),
                        "-c:a", "aac", str(seg_audio),
                    ]
                )
            else:
                # No narration for this scene - silence for its full video
                # length keeps the concatenated audio track continuous and
                # every later scene's audio correctly aligned.
                self._run(
                    [
                        "ffmpeg", "-y",
                        "-f", "lavfi", "-i", f"anullsrc=r={_AUDIO_SAMPLE_RATE}:cl=mono",
                        "-t", f"{video_duration:.3f}",
                        "-ar", str(_AUDIO_SAMPLE_RATE), "-ac", str(_AUDIO_CHANNELS),
                        "-c:a", "aac",
                        str(seg_audio),
                    ]
                )
            audio_parts.append(seg_audio)

        combined_video = work_dir / "combined_video.mp4"
        combined_audio = work_dir / "combined_audio.m4a"
        self._concat(video_parts, combined_video, work_dir)
        self._concat(audio_parts, combined_audio, work_dir)

        logs = self._run(
            [
                "ffmpeg", "-y",
                "-i", str(combined_video),
                "-i", str(combined_audio),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac",
                "-movflags", "+faststart",
                str(output_path),
            ]
        )
        logger.info(
            "ffmpeg_synced_assembly_complete",
            scene_count=len(segments),
            video_duration=self._probe_duration(combined_video),
            audio_duration=self._probe_duration(combined_audio),
        )
        return logs

    def _concat(self, parts: list[Path], output_path: Path, work_dir: Path) -> None:
        list_file = work_dir / f"{output_path.stem}_list.txt"
        list_file.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
        self._run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output_path)])

    def _probe_duration(self, path: Path) -> float:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise FFmpegError(f"ffprobe failed for {path}", logs=result.stderr)
        return float(result.stdout.strip())

    def generate_thumbnail(self, video_path: Path, thumbnail_path: Path, *, at_seconds: float = 1.0) -> str:
        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(at_seconds),
            "-i", str(video_path),
            "-vframes", "1",
            str(thumbnail_path),
        ]
        return self._run(cmd)

    def _run(self, cmd: list[str]) -> str:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            raise FFmpegError(f"ffmpeg timed out after {self.timeout_seconds}s", logs=str(exc)) from exc

        if result.returncode != 0:
            raise FFmpegError(f"ffmpeg exited with code {result.returncode}", logs=result.stderr)
        return result.stderr
