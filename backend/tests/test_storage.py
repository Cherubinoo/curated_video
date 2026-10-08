from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.services.storage.local_storage import LocalStorageService
from app.services.storage.path_utils import sanitize_relative_path


def test_sanitize_relative_path_accepts_safe_paths():
    assert sanitize_relative_path("videos/abc/versions/1/final.mp4") == "videos/abc/versions/1/final.mp4"


def test_sanitize_relative_path_normalizes_single_dot_segments():
    # "." segments are inert (they don't escape the root) and PurePosixPath
    # normalizes them away on its own - this is expected, safe behavior,
    # unlike ".." which is rejected below.
    assert sanitize_relative_path("videos/./final.mp4") == "videos/final.mp4"


@pytest.mark.parametrize(
    "bad_path",
    [
        "../etc/passwd",
        "/etc/passwd",
        "videos/../../../etc/passwd",
        "",
        "videos/final mp4",  # space not allowed
        "videos/<script>.mp4",
    ],
)
def test_sanitize_relative_path_rejects_unsafe_paths(bad_path):
    with pytest.raises(ValueError):
        sanitize_relative_path(bad_path)


def test_local_storage_save_and_open_roundtrip(tmp_path):
    storage = LocalStorageService(root=tmp_path, public_base_url="http://localhost:8000/media")

    src = tmp_path / "source.txt"
    src.write_text("hello world")

    key = storage.save("videos/v1/output.txt", src)
    assert key == "videos/v1/output.txt"
    assert storage.exists(key)
    assert storage.open(key).read_text() == "hello world"
    assert storage.get_url(key) == "http://localhost:8000/media/videos/v1/output.txt"


def test_local_storage_rejects_path_traversal_on_save(tmp_path):
    storage = LocalStorageService(root=tmp_path, public_base_url="http://localhost:8000/media")
    src = tmp_path / "source.txt"
    src.write_text("hello")

    with pytest.raises(ValueError):
        storage.save("../outside.txt", src)


def test_local_storage_delete(tmp_path):
    storage = LocalStorageService(root=tmp_path, public_base_url="http://localhost:8000/media")
    src = tmp_path / "source.txt"
    src.write_text("hello")
    storage.save("f.txt", src)

    assert storage.exists("f.txt")
    storage.delete("f.txt")
    assert not storage.exists("f.txt")


def test_local_storage_delete_prefix_removes_every_version(tmp_path):
    storage = LocalStorageService(root=tmp_path, public_base_url="http://localhost:8000/media")
    src = tmp_path / "source.txt"
    src.write_text("hello")

    storage.save("videos/abc/versions/1/final.mp4", src)
    storage.save("videos/abc/versions/2/final.mp4", src)
    storage.save("videos/other/versions/1/final.mp4", src)

    storage.delete_prefix("videos/abc")

    assert not storage.exists("videos/abc/versions/1/final.mp4")
    assert not storage.exists("videos/abc/versions/2/final.mp4")
    assert storage.exists("videos/other/versions/1/final.mp4")  # untouched


def test_local_storage_delete_prefix_on_missing_path_is_a_noop(tmp_path):
    storage = LocalStorageService(root=tmp_path, public_base_url="http://localhost:8000/media")
    storage.delete_prefix("videos/does-not-exist")  # must not raise


def test_local_storage_delete_prefix_refuses_the_storage_root(tmp_path):
    storage = LocalStorageService(root=tmp_path, public_base_url="http://localhost:8000/media")
    with pytest.raises(ValueError):
        storage.delete_prefix("")
