"""The render job lifecycle (product spec Section 9): validate, build,
render, post-process, upload, complete - or fail cleanly at any stage
without taking the worker process down with it.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from animation_engine.renderer.ffmpeg_processor import FFmpegError, FFmpegService, SceneAudioSegment
from animation_engine.renderer.manim_renderer import ManimRenderError, ManimRenderer
from animation_engine.validators.specification_validator import validate_specification
from app.core.celery_app import celery_app
from app.core.logging import bind_job_context, clear_job_context, get_logger
from app.db.session import session_scope
from app.models.asset import Asset
from app.models.enums import AssetType, RenderJobStatus, RenderStage, VideoStatus
from app.models.render_job import RenderJob
from app.models.video import Video
from app.models.video_specification import VideoSpecification
from app.services.audio import get_audio_service
from app.services.storage.factory import get_storage_service

logger = get_logger(__name__)

# Truncate anything shown to the user / stored on the row; full detail always
# stays in server-side structured logs (never a raw stack trace to the UI).
_MAX_ERROR_MESSAGE_LEN = 1000
_MAX_LOG_TAIL_LEN = 4000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _fail(db, job: RenderJob, video: Video | None, message: str) -> None:
    job.status = RenderJobStatus.FAILED
    job.stage = RenderStage.FAILED
    job.error_message = message[:_MAX_ERROR_MESSAGE_LEN]
    job.completed_at = _utcnow()
    job.append_log(f"FAILED: {message}")
    if video is not None:
        video.status = VideoStatus.FAILED
    db.commit()
    logger.error("render_job_failed", job_id=str(job.id), error=message)


@celery_app.task(bind=True, name="render_video_task")
def render_video_task(self, job_id: str) -> None:
    work_dir = Path(tempfile.mkdtemp(prefix="dsa-render-"))
    bind_job_context(job_id=job_id, worker_id=self.request.hostname or "unknown")

    try:
        with session_scope() as db:
            job = db.get(RenderJob, uuid.UUID(job_id))
            if job is None:
                logger.error("render_job_not_found", job_id=job_id)
                return

            video = db.get(Video, job.video_id)
            spec_row = db.get(VideoSpecification, job.specification_id) if job.specification_id else None
            bind_job_context(job_id=job_id, video_id=str(job.video_id))

            job.status = RenderJobStatus.RUNNING
            job.started_at = _utcnow()
            job.stage = RenderStage.VALIDATING
            job.progress = 5
            job.append_log("Validating specification.")
            if video is not None:
                video.status = VideoStatus.PROCESSING
            db.commit()

            if spec_row is None:
                _fail(db, job, video, "No specification attached to this render job.")
                return

            # Re-validate here too, even though the API already validated on
            # creation - the worker never trusts the database blindly.
            result = validate_specification(spec_row.specification_json)
            if not result.is_valid:
                _fail(db, job, video, "Specification failed validation: " + "; ".join(result.errors))
                return
            specification = result.specification

            job.stage = RenderStage.GENERATING_ANIMATION
            job.progress = 15
            job.append_log("Preparing render working directory.")
            db.commit()

            job.stage = RenderStage.RENDERING_MANIM
            job.progress = 20
            job.append_log("Starting Manim render.")
            db.commit()

            def _on_progress(scene_index: int, total_scenes: int) -> None:
                fraction = (scene_index / total_scenes) if total_scenes else 1.0
                job.progress = min(80, 20 + int(fraction * 60))
                db.commit()

            renderer = ManimRenderer()
            try:
                render_result = renderer.render(
                    specification, work_dir / "manim", progress_callback=_on_progress
                )
            except ManimRenderError as exc:
                job.append_log("Manim output (tail):\n" + exc.logs[-_MAX_LOG_TAIL_LEN:])
                _fail(db, job, video, f"Manim rendering failed: {exc}")
                return

            job.append_log("Manim render complete.")
            job.stage = RenderStage.PROCESSING_VIDEO
            job.progress = 85
            db.commit()

            ffmpeg = FFmpegService()
            final_path = work_dir / "final.mp4"
            thumbnail_path = work_dir / "thumbnail.jpg"
            audio_cleanup_paths: list[Path] = []

            try:
                # Preferred path: synthesize each scene's OWN narration and
                # sync it to that scene's actual rendered timing (see
                # ManimRenderResult.scene_timeline / FFmpegService.
                # assemble_synced_video) - this is what keeps narration from
                # drifting out of sync with the visuals over a long video, a
                # real observed bug with the old single whole-video track.
                used_synced_assembly = False
                if specification.audio.enabled and render_result.scene_timeline:
                    job.append_log("Synthesizing per-scene narration audio.")
                    db.commit()
                    audio_service = get_audio_service()
                    scenes_by_id = {s.id: s for s in specification.scenes}
                    segments: list[SceneAudioSegment] = []
                    any_narration = False
                    for entry in render_result.scene_timeline:
                        scene = scenes_by_id.get(entry["id"])
                        narration_text = scene.narration.strip() if scene and scene.narration else ""
                        seg_audio_path: Path | None = None
                        if narration_text:
                            synthesized = audio_service.synthesize(narration_text)
                            if synthesized is not None:
                                any_narration = True
                                seg_audio_path = Path(synthesized)
                                audio_cleanup_paths.append(seg_audio_path)
                        segments.append(
                            SceneAudioSegment(
                                scene_id=entry["id"],
                                start=entry["start"],
                                end=entry["end"],
                                audio_path=seg_audio_path,
                            )
                        )

                    if any_narration:
                        try:
                            ffmpeg.assemble_synced_video(
                                render_result.video_path,
                                final_path,
                                width=specification.settings.width,
                                height=specification.settings.height,
                                fps=specification.settings.fps,
                                segments=segments,
                                work_dir=work_dir / "assembly",
                            )
                            used_synced_assembly = True
                            job.append_log("Per-scene narration synthesized and synced to each scene's own timing.")
                        except FFmpegError as exc:
                            logger.warning("synced_assembly_failed_falling_back", job_id=job_id, error=str(exc))
                            job.append_log("Per-scene sync step failed - falling back to a single narration track.")
                    else:
                        job.append_log("No scene produced narration - continuing without audio.")
                    db.commit()

                if not used_synced_assembly:
                    # Fallback: no scene timeline was recorded, no scene had
                    # narration, or synced assembly itself failed - use one
                    # whole-video narration track as before.
                    audio_path: Path | None = None
                    if specification.audio.enabled and specification.audio.narration_script:
                        job.append_log("Synthesizing narration audio.")
                        db.commit()
                        audio_service = get_audio_service()
                        synthesized = audio_service.synthesize(specification.audio.narration_script)
                        if synthesized is not None:
                            audio_path = Path(synthesized)
                            audio_cleanup_paths.append(audio_path)
                        job.append_log(
                            "Narration audio ready."
                            if audio_path
                            else "Narration audio unavailable - continuing without it."
                        )
                        db.commit()
                    ffmpeg.finalize(
                        render_result.video_path,
                        final_path,
                        width=specification.settings.width,
                        height=specification.settings.height,
                        fps=specification.settings.fps,
                        audio_path=audio_path,
                    )

                ffmpeg.generate_thumbnail(final_path, thumbnail_path)
            except FFmpegError as exc:
                job.append_log("FFmpeg output (tail):\n" + exc.logs[-_MAX_LOG_TAIL_LEN:])
                _fail(db, job, video, f"Video post-processing failed: {exc}")
                return
            finally:
                for cleanup_path in audio_cleanup_paths:
                    cleanup_path.unlink(missing_ok=True)

            job.stage = RenderStage.UPLOADING
            job.progress = 95
            job.append_log("Uploading final assets to storage.")
            db.commit()

            storage = get_storage_service()
            base_key = f"videos/{video.id}/versions/{spec_row.version}"

            spec_key = storage.save_bytes(
                f"{base_key}/specification.json",
                json.dumps(spec_row.specification_json, indent=2).encode("utf-8"),
            )
            video_key = storage.save(f"{base_key}/final.mp4", final_path)
            thumbnail_key = storage.save(f"{base_key}/thumbnail.jpg", thumbnail_path)

            db.add_all(
                [
                    Asset(video_id=video.id, type=AssetType.SPECIFICATION, path=spec_key),
                    Asset(video_id=video.id, type=AssetType.FINAL_VIDEO, path=video_key),
                    Asset(video_id=video.id, type=AssetType.THUMBNAIL, path=thumbnail_key),
                ]
            )

            video.video_url = storage.get_url(video_key)
            video.thumbnail_url = storage.get_url(thumbnail_key)
            video.status = VideoStatus.COMPLETED

            job.status = RenderJobStatus.COMPLETED
            job.stage = RenderStage.COMPLETED
            job.progress = 100
            job.completed_at = _utcnow()
            job.append_log("Render complete.")
            db.commit()
            logger.info("render_job_completed", job_id=job_id, video_id=str(video.id))

    except Exception as exc:  # noqa: BLE001 - a render job failing must never crash the worker
        logger.error("render_job_unhandled_exception", job_id=job_id, error=str(exc), traceback=traceback.format_exc())
        try:
            with session_scope() as db:
                job = db.get(RenderJob, uuid.UUID(job_id))
                video = db.get(Video, job.video_id) if job else None
                if job is not None:
                    _fail(db, job, video, f"Unexpected worker error: {exc}")
        except Exception:  # noqa: BLE001 - best-effort failure recording only
            logger.error("render_job_failure_recording_failed", job_id=job_id, traceback=traceback.format_exc())
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        clear_job_context()
