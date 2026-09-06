from __future__ import annotations

import io
import shutil
from pathlib import Path

import pytest
from app.api.v1.meetings import (
    get_audio_storage_service,
    get_transcription_service,
)
from app.core.config import Settings
from app.main import app
from app.services.audio_storage import AudioStorageService
from app.services.transcription import (
    FasterWhisperService,
    GroqWhisperService,
    MockSpeechToTextService,
    SegmentData,
    TranscriptionResult,
    get_speech_to_text_service,
)
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def setup_test_environment(tmp_path: Path):
    test_storage_path = tmp_path / "test_storage"
    test_storage_path.mkdir(parents=True, exist_ok=True)

    storage_service = AudioStorageService(
        base_storage_path=test_storage_path, max_size_mb=10
    )
    mock_stt = MockSpeechToTextService()

    app.dependency_overrides[get_audio_storage_service] = lambda: storage_service
    app.dependency_overrides[get_transcription_service] = lambda: mock_stt

    yield test_storage_path, mock_stt

    app.dependency_overrides.pop(get_audio_storage_service, None)
    app.dependency_overrides.pop(get_transcription_service, None)
    if test_storage_path.exists():
        shutil.rmtree(test_storage_path, ignore_errors=True)


def test_transcribe_meeting_success(client: TestClient, setup_test_environment) -> None:
    _, mock_stt = setup_test_environment

    # 1. Cria reunião
    meeting_resp = client.post("/meetings", json={"title": "Reunião de Arquitetura"})
    assert meeting_resp.status_code == 201
    meeting_id = meeting_resp.json()["id"]

    # 2. Faz upload de áudio
    audio_content = b"fake-audio-bytes-for-transcription"
    files = {"file": ("reuniao.mp3", io.BytesIO(audio_content), "audio/mpeg")}
    upload_resp = client.post(f"/meetings/{meeting_id}/audio", files=files)
    assert upload_resp.status_code == 201

    # 3. Dispara transcrição
    transcribe_resp = client.post(f"/meetings/{meeting_id}/transcribe")
    assert transcribe_resp.status_code == 200
    data = transcribe_resp.json()

    # Validação da chamada ao serviço de STT
    assert mock_stt.call_count == 1
    assert "reuniao.mp3" in str(mock_stt.last_audio_path)
    assert mock_stt.last_language == "pt"

    # Validação do retorno da transcrição
    assert data["meeting_id"] == meeting_id
    assert "Bom dia a todos" in data["text"]
    assert data["text"] == data["content"]
    assert len(data["segments"]) == 2
    assert data["segments"][0]["start_time"] == 0.0
    assert data["segments"][0]["end_time"] == 3.5
    assert "Bom dia" in data["segments"][0]["text"]

    # 4. Verifica se o status da reunião mudou para "transcribed"
    meeting_check = client.get(f"/meetings/{meeting_id}")
    assert meeting_check.status_code == 200
    assert meeting_check.json()["status"] == "transcribed"
    assert meeting_check.json()["transcript"] is not None
    assert meeting_check.json()["transcript"]["content"] == data["content"]


def test_transcribe_meeting_not_found(client: TestClient) -> None:
    response = client.post("/meetings/99999/transcribe")
    assert response.status_code == 404
    assert "não encontrada" in response.json()["detail"]


def test_transcribe_meeting_invalid_id(client: TestClient) -> None:
    response = client.post("/meetings/-1/transcribe")
    assert response.status_code == 400


def test_transcribe_meeting_without_audio(client: TestClient) -> None:
    meeting_resp = client.post("/meetings", json={"title": "Reunião Sem Áudio"})
    meeting_id = meeting_resp.json()["id"]

    response = client.post(f"/meetings/{meeting_id}/transcribe")
    assert response.status_code == 404
    assert "Arquivo de áudio não encontrado" in response.json()["detail"]


def test_transcribe_audio_missing_on_disk(
    client: TestClient, setup_test_environment
) -> None:
    test_storage, _ = setup_test_environment

    meeting_resp = client.post("/meetings", json={"title": "Reunião Arquivo Deletado"})
    meeting_id = meeting_resp.json()["id"]

    files = {"file": ("audio.mp3", io.BytesIO(b"audio-bytes"), "audio/mpeg")}
    upload_resp = client.post(f"/meetings/{meeting_id}/audio", files=files)
    assert upload_resp.status_code == 201

    # Remove o arquivo do disco para simular perda de arquivo
    meeting_storage_dir = test_storage / str(meeting_id)
    shutil.rmtree(meeting_storage_dir)

    response = client.post(f"/meetings/{meeting_id}/transcribe")
    assert response.status_code == 404
    assert "não encontrado no armazenamento" in response.json()["detail"]


def test_transcribe_stt_service_failure(client: TestClient) -> None:
    meeting_resp = client.post("/meetings", json={"title": "Reunião Falha STT"})
    meeting_id = meeting_resp.json()["id"]

    files = {"file": ("audio.mp3", io.BytesIO(b"audio-bytes"), "audio/mpeg")}
    client.post(f"/meetings/{meeting_id}/audio", files=files)

    # Simula erro de API ou execução no provider de STT
    class FailingSTTService(MockSpeechToTextService):
        def transcribe(self, audio_path, language="pt"):
            raise RuntimeError("Conexão interrompida com o serviço de STT")

    app.dependency_overrides[get_transcription_service] = FailingSTTService

    response = client.post(f"/meetings/{meeting_id}/transcribe")
    assert response.status_code == 502
    assert "Falha no serviço de Speech-to-Text" in response.json()["detail"]

    # Valida que o status da reunião não ficou travado em "transcribing"
    meeting_data = client.get(f"/meetings/{meeting_id}").json()
    assert meeting_data["status"] == "audio_uploaded"


def test_transcribe_stt_empty_response(client: TestClient) -> None:
    meeting_resp = client.post("/meetings", json={"title": "Reunião Áudio Mudo"})
    meeting_id = meeting_resp.json()["id"]

    files = {"file": ("audio.mp3", io.BytesIO(b"audio-bytes"), "audio/mpeg")}
    client.post(f"/meetings/{meeting_id}/audio", files=files)

    # Simula retorno vazio do STT (áudio inaudível ou sem voz)
    empty_mock = MockSpeechToTextService(
        canned_result=TranscriptionResult(text="", segments=[])
    )
    app.dependency_overrides[get_transcription_service] = lambda: empty_mock

    response = client.post(f"/meetings/{meeting_id}/transcribe")
    assert response.status_code == 422
    assert "resposta vazia" in response.json()["detail"]

    # Status revertido para permitir retentativa
    meeting_data = client.get(f"/meetings/{meeting_id}").json()
    assert meeting_data["status"] == "audio_uploaded"


def test_transcribe_unexpected_read_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    meeting_resp = client.post("/meetings", json={"title": "Reunião Erro IO"})
    meeting_id = meeting_resp.json()["id"]

    files = {"file": ("audio.mp3", io.BytesIO(b"audio-bytes"), "audio/mpeg")}
    client.post(f"/meetings/{meeting_id}/audio", files=files)

    # Simula falha de leitura I/O do disco
    import builtins

    real_open = builtins.open

    def failing_open(file, *args, **kwargs):
        if str(file).endswith(".mp3"):
            raise OSError("Falha física de I/O no disco")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", failing_open)

    response = client.post(f"/meetings/{meeting_id}/transcribe")
    assert response.status_code == 500
    assert "Erro inesperado durante a leitura" in response.json()["detail"]


def test_get_transcript_success(client: TestClient) -> None:
    # 1. Cria, envia áudio e transcreve
    meeting_resp = client.post("/meetings", json={"title": "Reunião Teste GET"})
    meeting_id = meeting_resp.json()["id"]

    files = {"file": ("audio.mp3", io.BytesIO(b"audio-bytes"), "audio/mpeg")}
    client.post(f"/meetings/{meeting_id}/audio", files=files)
    client.post(f"/meetings/{meeting_id}/transcribe")

    # 2. Busca transcrição diretamente
    get_resp = client.get(f"/meetings/{meeting_id}/transcript")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["meeting_id"] == meeting_id
    assert "Bom dia a todos" in data["text"]
    assert data["text"] == data["content"]
    assert len(data["segments"]) == 2


def test_get_transcript_not_found(client: TestClient) -> None:
    meeting_resp = client.post("/meetings", json={"title": "Reunião Não Transcrita"})
    meeting_id = meeting_resp.json()["id"]

    response = client.get(f"/meetings/{meeting_id}/transcript")
    assert response.status_code == 404
    assert "Transcrição não encontrada" in response.json()["detail"]


def test_get_transcript_meeting_not_found(client: TestClient) -> None:
    response = client.get("/meetings/99999/transcript")
    assert response.status_code == 404


def test_retranscribe_replaces_old_transcript(client: TestClient) -> None:
    # 1. Cria reunião e upload
    meeting_resp = client.post("/meetings", json={"title": "Reunião Dupla Transcrição"})
    meeting_id = meeting_resp.json()["id"]

    files = {"file": ("audio.mp3", io.BytesIO(b"audio-bytes"), "audio/mpeg")}
    client.post(f"/meetings/{meeting_id}/audio", files=files)

    # 2. Primeira transcrição
    first_resp = client.post(f"/meetings/{meeting_id}/transcribe")
    assert first_resp.status_code == 200
    first_id = first_resp.json()["id"]

    # 3. Customiza mock para segundo resultado
    custom_mock = MockSpeechToTextService(
        canned_result=TranscriptionResult(
            text="Novo conteúdo transcrito atualizado.",
            segments=[
                SegmentData(
                    start=1.0,
                    end=4.0,
                    text="Novo conteúdo transcrito atualizado.",
                )
            ],
            language="pt",
            duration=4.0,
        )
    )
    app.dependency_overrides[get_transcription_service] = lambda: custom_mock

    # 4. Segunda transcrição para a mesma reunião
    second_resp = client.post(f"/meetings/{meeting_id}/transcribe")
    assert second_resp.status_code == 200
    data = second_resp.json()
    assert data["id"] == first_id
    assert data["content"] == "Novo conteúdo transcrito atualizado."
    assert len(data["segments"]) == 1
    assert data["segments"][0]["text"] == "Novo conteúdo transcrito atualizado."


def test_speech_to_text_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    # Sem GROQ_API_KEY -> FasterWhisperService
    monkeypatch.setattr(
        "app.services.transcription.base.settings",
        Settings(groq_api_key=None),
    )
    service_local = get_speech_to_text_service()
    assert isinstance(service_local, FasterWhisperService)
    assert service_local.vad_filter is True

    # Com GROQ_API_KEY -> GroqWhisperService
    monkeypatch.setattr(
        "app.services.transcription.base.settings",
        Settings(groq_api_key="gsk_fake_key_12345"),
    )
    service_cloud = get_speech_to_text_service()
    assert isinstance(service_cloud, GroqWhisperService)
    assert service_cloud.api_key == "gsk_fake_key_12345"


def test_groq_whisper_service_missing_credentials() -> None:
    with pytest.raises(ValueError, match="Chave de API da Groq ausente ou inválida"):
        GroqWhisperService(api_key="")

    with pytest.raises(ValueError, match="Chave de API da Groq ausente ou inválida"):
        GroqWhisperService(api_key="   ")
