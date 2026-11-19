from __future__ import annotations

import io
import shutil
from pathlib import Path

import pytest
from app.api.v1.meetings import get_audio_storage_service
from app.main import app
from app.services.audio_storage import AudioStorageService
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.datastructures import Headers, UploadFile


@pytest.fixture
def storage_service(tmp_path: Path) -> AudioStorageService:
    test_storage = tmp_path / "audio_storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    return AudioStorageService(base_storage_path=test_storage, max_size_mb=10)


@pytest.fixture
def temp_storage_for_client(tmp_path: Path):
    test_storage = tmp_path / "endpoint_audio_storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    service = AudioStorageService(base_storage_path=test_storage, max_size_mb=10)

    app.dependency_overrides[get_audio_storage_service] = lambda: service
    yield test_storage
    app.dependency_overrides.pop(get_audio_storage_service, None)
    if test_storage.exists():
        shutil.rmtree(test_storage, ignore_errors=True)


def test_service_validate_webm_codecs_opus(
    storage_service: AudioStorageService,
) -> None:
    upload = UploadFile(
        file=io.BytesIO(b"webm-audio-data"),
        filename="meeting_record.webm",
        headers=Headers({"content-type": "audio/webm;codecs=opus"}),
    )

    ext, content_type = storage_service.validate_file_metadata(upload)

    assert ext == ".webm"
    assert content_type == "audio/webm"


def test_service_validate_ogg_codecs_opus(
    storage_service: AudioStorageService,
) -> None:
    upload = UploadFile(
        file=io.BytesIO(b"ogg-audio-data"),
        filename="meeting_record.ogg",
        headers=Headers({"content-type": "audio/ogg;codecs=opus"}),
    )

    ext, content_type = storage_service.validate_file_metadata(upload)

    assert ext == ".ogg"
    assert content_type == "audio/ogg"


def test_service_validate_mp4_with_m4a(
    storage_service: AudioStorageService,
) -> None:
    upload = UploadFile(
        file=io.BytesIO(b"m4a-audio-data"),
        filename="meeting_record.m4a",
        headers=Headers({"content-type": "audio/mp4"}),
    )

    ext, content_type = storage_service.validate_file_metadata(upload)

    assert ext == ".m4a"
    assert content_type == "audio/mp4"


def test_service_validate_empty_file_zero_size(
    storage_service: AudioStorageService,
) -> None:
    upload = UploadFile(
        file=io.BytesIO(b""),
        size=0,
        filename="empty.webm",
        headers=Headers({"content-type": "audio/webm;codecs=opus"}),
    )

    with pytest.raises(HTTPException) as exc_info:
        storage_service.validate_file_metadata(upload)

    assert exc_info.value.status_code == 400
    assert "vazio" in exc_info.value.detail.lower()


def test_service_save_audio_empty_file_stream(
    storage_service: AudioStorageService,
) -> None:
    upload = UploadFile(
        file=io.BytesIO(b""),
        filename="empty_stream.ogg",
        headers=Headers({"content-type": "audio/ogg;codecs=opus"}),
    )

    with pytest.raises(HTTPException) as exc_info:
        storage_service.save_audio_file(meeting_id=1, file=upload)

    assert exc_info.value.status_code == 400
    assert "vazio" in exc_info.value.detail.lower()


def test_service_validate_unsupported_mime(
    storage_service: AudioStorageService,
) -> None:
    upload = UploadFile(
        file=io.BytesIO(b"not-audio"),
        filename="document.webm",
        headers=Headers({"content-type": "application/pdf"}),
    )

    with pytest.raises(HTTPException) as exc_info:
        storage_service.validate_file_metadata(upload)

    assert exc_info.value.status_code == 400
    assert "mime type" in exc_info.value.detail.lower()


def test_service_validate_unsupported_extension(
    storage_service: AudioStorageService,
) -> None:
    upload = UploadFile(
        file=io.BytesIO(b"some-content"),
        filename="audio.flac",
        headers=Headers({"content-type": "audio/webm"}),
    )

    with pytest.raises(HTTPException) as exc_info:
        storage_service.validate_file_metadata(upload)

    assert exc_info.value.status_code == 400
    assert "não suportado" in exc_info.value.detail.lower()


def test_upload_endpoint_webm_codecs_opus(
    client: TestClient,
    temp_storage_for_client: Path,
) -> None:
    meeting_resp = client.post("/meetings", json={"title": "WebM Opus Meeting"})
    assert meeting_resp.status_code == 201
    meeting_id = meeting_resp.json()["id"]

    audio_bytes = b"fake-webm-opus-binary-audio"
    files = {
        "file": (
            "recording.webm",
            io.BytesIO(audio_bytes),
            "audio/webm;codecs=opus",
        ),
    }

    resp = client.post(f"/meetings/{meeting_id}/audio", files=files)

    assert resp.status_code == 201
    data = resp.json()
    assert data["meeting_id"] == meeting_id
    assert data["original_filename"] == "recording.webm"
    assert data["content_type"] == "audio/webm"
    assert data["file_size_bytes"] == len(audio_bytes)


def test_upload_endpoint_ogg_codecs_opus(
    client: TestClient,
    temp_storage_for_client: Path,
) -> None:
    meeting_resp = client.post("/meetings", json={"title": "OGG Opus Meeting"})
    assert meeting_resp.status_code == 201
    meeting_id = meeting_resp.json()["id"]

    audio_bytes = b"fake-ogg-opus-binary-audio"
    files = {
        "file": (
            "recording.ogg",
            io.BytesIO(audio_bytes),
            "audio/ogg;codecs=opus",
        ),
    }

    resp = client.post(f"/meetings/{meeting_id}/audio", files=files)

    assert resp.status_code == 201
    data = resp.json()
    assert data["meeting_id"] == meeting_id
    assert data["original_filename"] == "recording.ogg"
    assert data["content_type"] == "audio/ogg"
    assert data["file_size_bytes"] == len(audio_bytes)


def test_upload_endpoint_mp4_m4a(
    client: TestClient,
    temp_storage_for_client: Path,
) -> None:
    meeting_resp = client.post("/meetings", json={"title": "M4A Meeting"})
    assert meeting_resp.status_code == 201
    meeting_id = meeting_resp.json()["id"]

    audio_bytes = b"fake-m4a-binary-audio"
    files = {
        "file": (
            "recording.m4a",
            io.BytesIO(audio_bytes),
            "audio/mp4",
        ),
    }

    resp = client.post(f"/meetings/{meeting_id}/audio", files=files)

    assert resp.status_code == 201
    data = resp.json()
    assert data["meeting_id"] == meeting_id
    assert data["original_filename"] == "recording.m4a"
    assert data["content_type"] == "audio/mp4"
    assert data["file_size_bytes"] == len(audio_bytes)


def test_upload_endpoint_empty_file_raises_400(
    client: TestClient,
    temp_storage_for_client: Path,
) -> None:
    meeting_resp = client.post("/meetings", json={"title": "Empty Audio Meeting"})
    assert meeting_resp.status_code == 201
    meeting_id = meeting_resp.json()["id"]

    files = {
        "file": (
            "empty.webm",
            io.BytesIO(b""),
            "audio/webm;codecs=opus",
        ),
    }

    resp = client.post(f"/meetings/{meeting_id}/audio", files=files)

    assert resp.status_code == 400
    assert "vazio" in resp.json()["detail"].lower()


def test_upload_endpoint_unsupported_mime_raises_400(
    client: TestClient,
    temp_storage_for_client: Path,
) -> None:
    meeting_resp = client.post("/meetings", json={"title": "Invalid MIME Meeting"})
    assert meeting_resp.status_code == 201
    meeting_id = meeting_resp.json()["id"]

    files = {
        "file": (
            "audio.webm",
            io.BytesIO(b"not-really-audio"),
            "application/zip",
        ),
    }

    resp = client.post(f"/meetings/{meeting_id}/audio", files=files)

    assert resp.status_code == 400
    assert "mime type" in resp.json()["detail"].lower()


def test_upload_endpoint_unsupported_extension_raises_400(
    client: TestClient,
    temp_storage_for_client: Path,
) -> None:
    meeting_resp = client.post("/meetings", json={"title": "Invalid Ext Meeting"})
    assert meeting_resp.status_code == 201
    meeting_id = meeting_resp.json()["id"]

    files = {
        "file": (
            "notes.docx",
            io.BytesIO(b"some content"),
            "audio/webm",
        ),
    }

    resp = client.post(f"/meetings/{meeting_id}/audio", files=files)

    assert resp.status_code == 400
    assert "não suportado" in resp.json()["detail"].lower()
