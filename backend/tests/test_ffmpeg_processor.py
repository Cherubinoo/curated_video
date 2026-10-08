"""`FFmpegService.finalize()`'s audio/video duration-matching logic.

Regression coverage for a real observed bug: the old `-shortest` mux flag
silently truncated the narration audio to match a shorter animation, so a
long, carefully-generated narration script got cut off mid-sentence in the
final video. Mocks `subprocess.run` throughout - no real ffmpeg/ffprobe
call, no real media files - to stay fast; the real muxing behavior is
exercised by the e2e Manim render test.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from animation_engine.renderer.ffmpeg_processor import (
    _AUDIO_CHANNELS,
    _AUDIO_SAMPLE_RATE,
    FFmpegService,
    SceneAudioSegment,
)


def _mock_probe_result(duration: str) -> MagicMock:
    result = MagicMock()
    result.returncode = 0
    result.stdout = duration
    result.stderr = ""
    return result


def test_no_audio_path_uses_an_and_skips_probing(tmp_path):
    service = FFmpegService()
    video = tmp_path / "in.mp4"
    video.touch()
    out = tmp_path / "out.mp4"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        service.finalize(video, out, width=1920, height=1080, fps=30, audio_path=None)

    cmd = mock_run.call_args.args[0]
    assert "-an" in cmd
    assert "-filter_complex" not in cmd


def test_audio_shorter_than_video_pads_audio_with_silence(tmp_path):
    service = FFmpegService()
    video = tmp_path / "in.mp4"
    video.touch()
    audio = tmp_path / "narration.mp3"
    audio.touch()
    out = tmp_path / "out.mp4"

    probe_results = [_mock_probe_result("300.0"), _mock_probe_result("140.0")]  # video, then audio
    run_results = probe_results + [MagicMock(returncode=0, stderr="")]

    with patch("subprocess.run", side_effect=run_results) as mock_run:
        service.finalize(video, out, width=1920, height=1080, fps=30, audio_path=audio)

    final_cmd = mock_run.call_args_list[-1].args[0]
    filter_complex = final_cmd[final_cmd.index("-filter_complex") + 1]
    assert "apad=pad_dur=160.000" in filter_complex  # 300 - 140
    assert "tpad" not in filter_complex  # video is the longer stream here


def test_video_shorter_than_audio_pads_video_by_holding_last_frame(tmp_path):
    """The exact scenario from the real bug: a long narration script (audio)
    outlasting the animation (video) - the video must be extended, not the
    audio truncated."""
    service = FFmpegService()
    video = tmp_path / "in.mp4"
    video.touch()
    audio = tmp_path / "narration.mp3"
    audio.touch()
    out = tmp_path / "out.mp4"

    probe_results = [_mock_probe_result("137.9"), _mock_probe_result("300.0")]  # video, then audio
    run_results = probe_results + [MagicMock(returncode=0, stderr="")]

    with patch("subprocess.run", side_effect=run_results) as mock_run:
        service.finalize(video, out, width=1920, height=1080, fps=30, audio_path=audio)

    final_cmd = mock_run.call_args_list[-1].args[0]
    assert "-shortest" not in final_cmd  # the old truncating behavior must be gone
    filter_complex = final_cmd[final_cmd.index("-filter_complex") + 1]
    assert "tpad=stop_mode=clone:stop_duration=162.100" in filter_complex  # 300 - 137.9
    assert "apad" not in filter_complex  # audio is the longer stream here


def test_probe_failure_falls_back_to_shortest_rather_than_failing(tmp_path):
    service = FFmpegService()
    video = tmp_path / "in.mp4"
    video.touch()
    audio = tmp_path / "narration.mp3"
    audio.touch()
    out = tmp_path / "out.mp4"

    failing_probe = MagicMock(returncode=1, stdout="", stderr="ffprobe exploded")
    run_results = [failing_probe, MagicMock(returncode=0, stderr="")]

    with patch("subprocess.run", side_effect=run_results) as mock_run:
        service.finalize(video, out, width=1920, height=1080, fps=30, audio_path=audio)

    final_cmd = mock_run.call_args_list[-1].args[0]
    assert "-shortest" in final_cmd


def _smart_run(probe_durations: dict[str, str]):
    """A `subprocess.run` fake that answers ffprobe calls with a
    per-path-configured duration and treats every other (ffmpeg) call as a
    clean success - avoids hardcoding the exact call order/count of
    `assemble_synced_video`'s many subprocess calls, which would make these
    tests brittle to harmless refactors."""

    def _run(cmd, **kwargs):
        if cmd[0] == "ffprobe":
            return _mock_probe_result(probe_durations.get(cmd[-1], "1.0"))
        return MagicMock(returncode=0, stderr="")

    return _run


class TestAssembleSyncedVideo:
    """`FFmpegService.assemble_synced_video()` - the per-scene sync
    pipeline (see workers/tasks.py) that replaced one whole-video narration
    track with each scene's own narration matched to that scene's actual
    rendered timing. Regression-tests the real bug found and fixed while
    building this: silence segments were generated at a different sample
    rate/channel layout (44100 Hz stereo) than Polly's real output (24000 Hz
    mono), and concatenating mismatched-format audio segments via the
    concat demuxer corrupted the resulting duration (41.75s reported for
    what should have been 22.7s of real audio)."""

    def test_uses_one_consistent_audio_format_for_every_segment(self, tmp_path):
        service = FFmpegService()
        video = tmp_path / "in.mp4"
        video.touch()
        audio1 = tmp_path / "a1.mp3"
        audio1.touch()
        out = tmp_path / "out.mp4"

        segments = [
            SceneAudioSegment(scene_id="s1", start=0.0, end=5.0, audio_path=audio1),
            SceneAudioSegment(scene_id="s2", start=5.0, end=10.0, audio_path=None),
        ]

        with patch(
            "subprocess.run", side_effect=_smart_run({str(audio1): "3.0"})
        ) as mock_run:
            service.assemble_synced_video(
                video, out, width=1920, height=1080, fps=30, segments=segments, work_dir=tmp_path / "work"
            )

        audio_cmds = [
            c.args[0]
            for c in mock_run.call_args_list
            if "-af" in c.args[0] or "anullsrc" in " ".join(c.args[0])
        ]
        assert len(audio_cmds) == 2  # one real (padded) segment + one silence segment
        for cmd in audio_cmds:
            assert str(_AUDIO_SAMPLE_RATE) in cmd
            assert str(_AUDIO_CHANNELS) in cmd

    def test_generates_silence_for_a_scene_with_no_narration(self, tmp_path):
        service = FFmpegService()
        video = tmp_path / "in.mp4"
        video.touch()
        out = tmp_path / "out.mp4"

        segments = [SceneAudioSegment(scene_id="s1", start=0.0, end=5.0, audio_path=None)]

        with patch("subprocess.run", side_effect=_smart_run({})) as mock_run:
            service.assemble_synced_video(
                video, out, width=1920, height=1080, fps=30, segments=segments, work_dir=tmp_path / "work"
            )

        silence_cmds = [c.args[0] for c in mock_run.call_args_list if "anullsrc" in " ".join(c.args[0])]
        assert len(silence_cmds) == 1
        assert "-t" in silence_cmds[0]
        assert "5.000" in silence_cmds[0]  # the scene's own video duration (5.0 - 0.0)

    def test_pads_video_when_narration_outlasts_its_own_scene(self, tmp_path):
        service = FFmpegService()
        video = tmp_path / "in.mp4"
        video.touch()
        audio = tmp_path / "a1.mp3"
        audio.touch()
        out = tmp_path / "out.mp4"

        # scene is 5s of video but its narration takes 9s to speak
        segments = [SceneAudioSegment(scene_id="s1", start=0.0, end=5.0, audio_path=audio)]

        with patch("subprocess.run", side_effect=_smart_run({str(audio): "9.0"})) as mock_run:
            service.assemble_synced_video(
                video, out, width=1920, height=1080, fps=30, segments=segments, work_dir=tmp_path / "work"
            )

        tpad_cmds = [c.args[0] for c in mock_run.call_args_list if "tpad" in " ".join(c.args[0])]
        assert len(tpad_cmds) == 1
        assert "stop_duration=4.000" in " ".join(tpad_cmds[0])  # 9.0 - 5.0
