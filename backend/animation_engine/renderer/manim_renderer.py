"""Isolated, timeout-bounded Manim subprocess wrapper.

Manim always runs as a separate process (never in-process with the API or
worker's own Python), with a hard wall-clock timeout, so a runaway or
malformed render can't hang the worker indefinitely - see product spec
Section 17 (isolate rendering process, limit render duration).
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

from app.core.config import settings
from app.schemas.specification import VideoSpecification

ProgressCallback = Callable[[int, int], None]

_QUALITY_FLAGS = {"low": "-ql", "medium": "-qm", "high": "-qh"}


class ManimRenderError(Exception):
    def __init__(self, message: str, logs: str = ""):
        super().__init__(message)
        self.logs = logs


class ManimRenderResult:
    def __init__(self, video_path: Path, logs: str, scene_timeline: list[dict] | None = None):
        self.video_path = video_path
        self.logs = logs
        # Each entry: {"id": scene_id, "start": seconds, "end": seconds} -
        # exact rendered timing from Manim's own clock (see
        # scene_builder.py's `_write_timeline`), used to synthesize and
        # align each scene's own narration to precisely when that scene
        # plays. `None`/empty if the timeline file couldn't be read for any
        # reason - callers must fall back to whole-video audio handling.
        self.scene_timeline = scene_timeline or []


class ManimRenderer:
    def __init__(self, backend_root: Path | None = None, timeout_seconds: int | None = None):
        # backend/animation_engine/renderer/manim_renderer.py -> backend/
        self.backend_root = backend_root or Path(__file__).resolve().parents[2]
        self.timeout_seconds = timeout_seconds or settings.render_timeout_seconds

    def render(
        self,
        specification: VideoSpecification,
        work_dir: Path,
        progress_callback: ProgressCallback | None = None,
    ) -> ManimRenderResult:
        work_dir.mkdir(parents=True, exist_ok=True)
        spec_path = work_dir / "specification.json"
        spec_path.write_text(specification.model_dump_json(), encoding="utf-8")
        progress_path = work_dir / "progress.json"
        timeline_path = work_dir / "scene_timeline.json"
        media_dir = work_dir / "media"

        quality_flag = _QUALITY_FLAGS.get(settings.manim_quality, "-qm")
        cmd = [
            "manim", "render", quality_flag,
            "--media_dir", str(media_dir),
            "--fps", str(specification.settings.fps),
            "-r", f"{specification.settings.width},{specification.settings.height}",
            "--disable_caching",
            str(self.backend_root / "manim_scenes" / "dynamic_scene.py"),
            "SpecificationScene",
        ]

        env = os.environ.copy()
        env["DSA_SPEC_PATH"] = str(spec_path)
        env["DSA_PROGRESS_PATH"] = str(progress_path)
        env["DSA_TIMELINE_PATH"] = str(timeline_path)
        # The `manim` console-script entry point loads dynamic_scene.py by
        # file path via importlib, which does NOT put its directory (or the
        # cwd) on sys.path the way `python script.py` would - so
        # `animation_engine`/`app` imports inside it fail unless we put the
        # backend root on PYTHONPATH explicitly.
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{self.backend_root}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else str(self.backend_root)
        )

        process = subprocess.Popen(
            cmd,
            cwd=str(self.backend_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        log_lines: list[str] = []

        def _drain_output() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                log_lines.append(line)

        reader_thread = threading.Thread(target=_drain_output, daemon=True)
        reader_thread.start()

        total_scenes = len(specification.scenes)
        last_reported_index = -1

        def _check_progress() -> None:
            nonlocal last_reported_index
            if not (progress_callback and total_scenes and progress_path.exists()):
                return
            try:
                data = json.loads(progress_path.read_text(encoding="utf-8"))
                scene_index = int(data.get("scene_index", 0))
                if scene_index != last_reported_index:
                    last_reported_index = scene_index
                    progress_callback(scene_index, total_scenes)
            except (json.JSONDecodeError, OSError, ValueError):
                pass

        start = time.monotonic()
        timed_out = False

        while process.poll() is None:
            if time.monotonic() - start > self.timeout_seconds:
                process.kill()
                timed_out = True
                break
            _check_progress()
            time.sleep(1.0)

        # A render that finishes faster than one poll tick (e.g. a single
        # short scene) would otherwise never get a progress callback at
        # all - the scene has already written its final progress.json by
        # the time the process exits, so check once more here.
        if not timed_out:
            _check_progress()

        reader_thread.join(timeout=5)
        logs = "".join(log_lines)

        if timed_out:
            raise ManimRenderError(
                f"Manim render exceeded the {self.timeout_seconds}s timeout and was killed.", logs=logs
            )
        if process.returncode != 0:
            raise ManimRenderError(f"Manim exited with code {process.returncode}.", logs=logs)

        output_path = self._find_output_video(media_dir)
        if output_path is None:
            raise ManimRenderError("Manim reported success but produced no output video file.", logs=logs)

        scene_timeline = self._read_timeline(timeline_path)
        return ManimRenderResult(video_path=output_path, logs=logs, scene_timeline=scene_timeline)

    @staticmethod
    def _read_timeline(timeline_path: Path) -> list[dict]:
        try:
            return json.loads(timeline_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []  # best-effort - callers fall back to whole-video audio handling

    @staticmethod
    def _find_output_video(media_dir: Path) -> Path | None:
        videos_dir = media_dir / "videos"
        if not videos_dir.exists():
            return None
        candidates = list(videos_dir.rglob("SpecificationScene.mp4"))
        if not candidates:
            candidates = list(videos_dir.rglob("*.mp4"))
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.stat().st_mtime)
