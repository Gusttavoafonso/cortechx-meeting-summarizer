import io
import shutil
from pathlib import Path

import pytest
from app.api.v1.meetings import get_audio_storage_service
from app.main import app
from app.services.audio_storage import AudioStorageService
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def cleanup_test_storage(tmp_path: Path):
    test_storage_path = tmp_path / "test_storage"
    test_storage_path.mkdir(parents=True, exist_ok=True)

    def override_storage_service():
        return AudioStorageService(base_storage_path=test_storage_path, max_size_mb=10)

    app.dependency_overrides[get_audio_storage_service] = override_storage_service
    yield test_storage_path
    app.dependency_overrides.pop(get_audio_storage_service, None)
    if test_storage_path.exists():
        shutil.rmtree(test_storage_path, ignore_errors=True)


def test_create_meeting(client: TestClient) -> None:
    response = client.post("/meetings", json={"title": "Reunião de Alinhamento"})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Reunião de Alinhamento"
    assert data["status"] == "received"
    assert "id" in data
    assert data["audio"] is None


def test_upload_audio_success(client: TestClient, cleanup_test_storage: Path) -> None:
    # 1. Cria reunião
    meeting_resp = client.post("/meetings", json={"title": "Sprint Planning"})
    assert meeting_resp.status_code == 201
    meeting_id = meeting_resp.json()["id"]

    # 2. Faz upload de áudio válido
    audio_content = b"fake-audio-binary-stream-12345"
    files = {
        "file": ("recording.mp3", io.BytesIO(audio_content), "audio/mpeg"),
    }
    response = client.post(f"/meetings/{meeting_id}/audio", files=files)

    assert response.status_code == 201
    data = response.json()
    assert data["meeting_id"] == meeting_id
    assert data["original_filename"] == "recording.mp3"
    assert data["content_type"] == "audio/mpeg"
    assert data["file_size_bytes"] == len(audio_content)
    assert "filename" in data
    assert "uploaded_at" in data

    # 3. Verifica se arquivo foi gravado no diretório
    meeting_dir = cleanup_test_storage / str(meeting_id)
    saved_files = list(meeting_dir.glob("*.mp3"))
    assert len(saved_files) == 1
    assert saved_files[0].read_bytes() == audio_content

    # 4. Verifica se status e metadados de áudio da reunião foram atualizados
    meeting_check = client.get(f"/meetings/{meeting_id}")
    assert meeting_check.status_code == 200
    meeting_data = meeting_check.json()
    assert meeting_data["status"] == "audio_uploaded"
    assert meeting_data["audio"] is not None
    assert meeting_data["audio"]["original_filename"] == "recording.mp3"
    assert meeting_data["audio"]["file_size_bytes"] == len(audio_content)


def test_get_audio_metadata(client: TestClient) -> None:
    # Cria reunião e envia áudio
    meeting_resp = client.post("/meetings", json={"title": "1on1"})
    meeting_id = meeting_resp.json()["id"]

    audio_content = b"wav-audio-content"
    files = {
        "file": ("call.wav", io.BytesIO(audio_content), "audio/wav"),
    }
    upload_resp = client.post(f"/meetings/{meeting_id}/audio", files=files)
    assert upload_resp.status_code == 201

    # Busca metadados via GET
    meta_resp = client.get(f"/meetings/{meeting_id}/audio")
    assert meta_resp.status_code == 200
    data = meta_resp.json()
    assert data["meeting_id"] == meeting_id
    assert data["original_filename"] == "call.wav"
    assert data["content_type"] == "audio/wav"
    assert data["file_size_bytes"] == len(audio_content)


def test_upload_audio_meeting_not_found(client: TestClient) -> None:
    files = {
        "file": ("sample.mp3", io.BytesIO(b"audio-bytes"), "audio/mpeg"),
    }
    response = client.post("/meetings/99999/audio", files=files)

    assert response.status_code == 404
    assert "não encontrada" in response.json()["detail"].lower()


def test_upload_audio_invalid_meeting_id_negative(client: TestClient) -> None:
    files = {
        "file": ("sample.mp3", io.BytesIO(b"audio-bytes"), "audio/mpeg"),
    }
    response = client.post("/meetings/-1/audio", files=files)

    assert response.status_code == 400
    assert "inválido" in response.json()["detail"].lower()


def test_upload_audio_invalid_meeting_id_zero(client: TestClient) -> None:
    files = {
        "file": ("sample.mp3", io.BytesIO(b"audio-bytes"), "audio/mpeg"),
    }
    response = client.post("/meetings/0/audio", files=files)

    assert response.status_code == 400
    assert "inválido" in response.json()["detail"].lower()


def test_upload_audio_invalid_meeting_id_string(client: TestClient) -> None:
    files = {
        "file": ("sample.mp3", io.BytesIO(b"audio-bytes"), "audio/mpeg"),
    }
    response = client.post("/meetings/invalid_id/audio", files=files)

    assert response.status_code == 422


def test_upload_audio_empty_file(client: TestClient) -> None:
    meeting_resp = client.post("/meetings", json={"title": "Daily"})
    meeting_id = meeting_resp.json()["id"]

    files = {
        "file": ("empty.mp3", io.BytesIO(b""), "audio/mpeg"),
    }
    response = client.post(f"/meetings/{meeting_id}/audio", files=files)

    assert response.status_code == 400
    assert "vazio" in response.json()["detail"].lower()


def test_upload_audio_invalid_extension(client: TestClient) -> None:
    meeting_resp = client.post("/meetings", json={"title": "Daily"})
    meeting_id = meeting_resp.json()["id"]

    files = {
        "file": ("notes.txt", io.BytesIO(b"just text"), "text/plain"),
    }
    response = client.post(f"/meetings/{meeting_id}/audio", files=files)

    assert response.status_code == 400
    assert "não suportado" in response.json()["detail"].lower()


def test_upload_audio_invalid_mime_type(client: TestClient) -> None:
    meeting_resp = client.post("/meetings", json={"title": "Daily"})
    meeting_id = meeting_resp.json()["id"]

    files = {
        "file": ("audio.mp3", io.BytesIO(b"fake audio"), "application/pdf"),
    }
    response = client.post(f"/meetings/{meeting_id}/audio", files=files)

    assert response.status_code == 400
    assert "mime type" in response.json()["detail"].lower()


def test_upload_audio_size_exceeded(client: TestClient, tmp_path: Path) -> None:
    meeting_resp = client.post("/meetings", json={"title": "Daily"})
    meeting_id = meeting_resp.json()["id"]

    test_storage_path = tmp_path / "test_storage_limit"
    test_storage_path.mkdir(parents=True, exist_ok=True)

    # Serviço configurado com limite de 0 MB (max_bytes = 10 bytes)
    custom_service = AudioStorageService(
        base_storage_path=test_storage_path, max_size_mb=1
    )
    custom_service.max_bytes = 10  # força limite em 10 bytes para teste

    app.dependency_overrides[get_audio_storage_service] = lambda: custom_service

    try:
        files = {
            "file": ("large.mp3", io.BytesIO(b"A" * 50), "audio/mpeg"),
        }
        response = client.post(f"/meetings/{meeting_id}/audio", files=files)

        assert response.status_code == 413
        assert "excede o limite" in response.json()["detail"].lower()

        # Garante que nenhum arquivo residual ficou no disco
        meeting_dir = test_storage_path / str(meeting_id)
        if meeting_dir.exists():
            assert len(list(meeting_dir.iterdir())) == 0
    finally:
        app.dependency_overrides.pop(get_audio_storage_service, None)


def test_get_meeting_not_found(client: TestClient) -> None:
    response = client.get("/meetings/99999")
    assert response.status_code == 404
    assert "não encontrada" in response.json()["detail"].lower()


def test_get_audio_metadata_not_found(client: TestClient) -> None:
    meeting_resp = client.post("/meetings", json={"title": "Retro"})
    meeting_id = meeting_resp.json()["id"]

    response = client.get(f"/meetings/{meeting_id}/audio")
    assert response.status_code == 404
    assert "áudio não encontrado" in response.json()["detail"].lower()


def test_upload_audio_replace_existing(
    client: TestClient, cleanup_test_storage: Path
) -> None:
    meeting_resp = client.post("/meetings", json={"title": "Demo"})
    meeting_id = meeting_resp.json()["id"]

    files_v1 = {
        "file": ("v1.mp3", io.BytesIO(b"audio-v1-bytes"), "audio/mpeg"),
    }
    resp1 = client.post(f"/meetings/{meeting_id}/audio", files=files_v1)
    assert resp1.status_code == 201
    assert resp1.json()["original_filename"] == "v1.mp3"

    files_v2 = {
        "file": ("v2.mp3", io.BytesIO(b"audio-v2-bytes-updated"), "audio/mpeg"),
    }
    resp2 = client.post(f"/meetings/{meeting_id}/audio", files=files_v2)
    assert resp2.status_code == 201
    assert resp2.json()["original_filename"] == "v2.mp3"
    assert resp2.json()["file_size_bytes"] == len(b"audio-v2-bytes-updated")

    # Verifica que o arquivo antigo foi removido e resta apenas
    # 1 arquivo na pasta da reunião
    meeting_dir = cleanup_test_storage / str(meeting_id)
    saved_files = list(meeting_dir.glob("*.mp3"))
    assert len(saved_files) == 1
    assert saved_files[0].read_bytes() == b"audio-v2-bytes-updated"


def test_storage_service_helper_methods(tmp_path: Path) -> None:
    service = AudioStorageService(base_storage_path=tmp_path)
    sample_file = tmp_path / "sample.mp3"
    sample_file.write_bytes(b"hello audio")

    # get_file_path
    resolved_path = service.get_file_path(str(sample_file))
    assert resolved_path == sample_file

    # file_exists
    assert service.file_exists(str(sample_file)) is True
    assert service.file_exists(str(tmp_path / "non_existent.mp3")) is False

    # delete_file
    assert service.delete_file(str(sample_file)) is True
    assert service.file_exists(str(sample_file)) is False
    assert service.delete_file(str(sample_file)) is False


def test_upload_audio_without_extension(client: TestClient) -> None:
    meeting_resp = client.post("/meetings", json={"title": "Demo"})
    meeting_id = meeting_resp.json()["id"]

    files = {
        "file": ("recording", io.BytesIO(b"content"), "audio/mpeg"),
    }
    response = client.post(f"/meetings/{meeting_id}/audio", files=files)
    assert response.status_code == 400
    assert "não possui extensão" in response.json()["detail"].lower()



@pytest.mark.parametrize(
    "filename,content_type",
    [
        ("audio.mp3", "audio/mpeg"),
        ("audio.wav", "audio/wav"),
        ("audio.m4a", "audio/m4a"),
        ("video.mp4", "video/mp4"),
        ("video.webm", "video/webm"),
    ],
)
def test_upload_audio_all_supported_formats(
    client: TestClient, filename: str, content_type: str
) -> None:
    meeting_resp = client.post("/meetings", json={"title": f"Format Test {filename}"})
    meeting_id = meeting_resp.json()["id"]

    files = {
        "file": (filename, io.BytesIO(b"valid-sample-binary-data"), content_type),
    }
    response = client.post(f"/meetings/{meeting_id}/audio", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == filename
    assert data["content_type"] == content_type
