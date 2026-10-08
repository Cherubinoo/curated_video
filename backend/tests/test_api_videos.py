from __future__ import annotations

from unittest.mock import patch


def test_create_video_requires_api_key(client):
    res = client.post("/api/videos", json={"title": "T", "topic": "demo", "prompt": "p", "duration": 60})
    assert res.status_code == 401


def test_create_video(client, auth_headers):
    res = client.post(
        "/api/videos",
        headers=auth_headers,
        json={"title": "T", "topic": "demo", "prompt": "p", "duration": 60},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "DRAFT"
    assert "id" in body


def test_create_video_rejects_invalid_payload(client, auth_headers):
    res = client.post(
        "/api/videos",
        headers=auth_headers,
        json={"title": "", "topic": "demo", "prompt": "p", "duration": 60},
    )
    assert res.status_code == 422


def test_get_video_not_found(client, auth_headers):
    res = client.get("/api/videos/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert res.status_code == 404


def test_list_videos(client, auth_headers):
    client.post(
        "/api/videos",
        headers=auth_headers,
        json={"title": "T1", "topic": "demo", "prompt": "p", "duration": 60},
    )
    res = client.get("/api/videos", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["total"] >= 1


@patch("app.services.video_service.VideoService.trigger_render")
def test_generate_video_enqueues_job(mock_trigger, client, auth_headers):
    import uuid as uuid_mod
    from datetime import datetime, timezone

    from app.models.enums import RenderJobStatus, RenderStage
    from app.models.render_job import RenderJob

    # Python-side column defaults (progress=0, logs="", created_at=utcnow)
    # only apply on INSERT flush - set them explicitly since this object is
    # never persisted.
    fake_job = RenderJob(
        id=uuid_mod.uuid4(),
        video_id=uuid_mod.uuid4(),
        status=RenderJobStatus.PENDING,
        stage=RenderStage.QUEUED,
        progress=0,
        logs="",
        created_at=datetime.now(timezone.utc),
    )
    mock_trigger.return_value = fake_job

    create_res = client.post(
        "/api/videos",
        headers=auth_headers,
        json={"title": "T", "topic": "demo", "prompt": "p", "duration": 60},
    )
    video_id = create_res.json()["id"]

    res = client.post(f"/api/videos/{video_id}/generate", headers=auth_headers)
    assert res.status_code == 202
    assert res.json()["status"] == "PENDING"
    mock_trigger.assert_called_once()


def test_delete_video_not_found(client, auth_headers):
    res = client.delete("/api/videos/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert res.status_code == 404


def test_delete_video_removes_it(client, auth_headers):
    create_res = client.post(
        "/api/videos",
        headers=auth_headers,
        json={"title": "To Delete", "topic": "demo", "prompt": "p", "duration": 60},
    )
    video_id = create_res.json()["id"]

    res = client.delete(f"/api/videos/{video_id}", headers=auth_headers)
    assert res.status_code == 204

    get_res = client.get(f"/api/videos/{video_id}", headers=auth_headers)
    assert get_res.status_code == 404


def test_delete_video_refuses_while_active(client, db_session, auth_headers):
    import uuid as uuid_mod

    from app.models.enums import VideoStatus
    from app.models.video import Video

    create_res = client.post(
        "/api/videos",
        headers=auth_headers,
        json={"title": "Active Video", "topic": "demo", "prompt": "p", "duration": 60},
    )
    video_id = create_res.json()["id"]

    video = db_session.get(Video, uuid_mod.UUID(video_id))
    video.status = VideoStatus.PROCESSING
    db_session.commit()

    res = client.delete(f"/api/videos/{video_id}", headers=auth_headers)
    assert res.status_code == 409

    # Untouched - still there.
    get_res = client.get(f"/api/videos/{video_id}", headers=auth_headers)
    assert get_res.status_code == 200


def test_video_status_endpoint(client, auth_headers):
    create_res = client.post(
        "/api/videos",
        headers=auth_headers,
        json={"title": "T", "topic": "demo", "prompt": "p", "duration": 60},
    )
    video_id = create_res.json()["id"]

    res = client.get(f"/api/videos/{video_id}/status", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "DRAFT"
    assert body["progress"] == 0
