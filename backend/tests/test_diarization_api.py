from pathlib import Path

import pytest
from app.api.v1.meetings import get_diarization_service
from app.core.config import Settings
from app.core.config import settings as app_settings
from app.main import app
from app.repositories.transcript_repository import TranscriptRepository
from app.services.diarization import (
    DiarizationProvider,
    DiarizationSegment,
    DiarizationService,
)
from app.services.transcription.base import SegmentData
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class FakeDiarizationProvider(DiarizationProvider):
    def __init__(self, segments: list[DiarizationSegment]) -> None:
        self.segments = segments

    def diarize(self, audio_path: Path) -> list[DiarizationSegment]:
        return self.segments


@pytest.fixture(autouse=True)
def setup_diarization_environment(tmp_path: Path):
    storage_path = tmp_path / "storage"
    storage_path.mkdir()
    previous_settings = app_settings.model_copy()
    app_settings.__dict__.update(
        Settings(base_storage_path=storage_path, max_size_mb=10).__dict__
    )
    yield
    app.dependency_overrides.pop(get_diarization_service, None)
    app_settings.__dict__.update(previous_settings.__dict__)


def create_meeting_with_audio_and_transcript(
    client: TestClient, db_session: Session
) -> int:
    meeting_response = client.post("/meetings", json={"title": "Reunião com falantes"})
    meeting_id = meeting_response.json()["id"]
    upload_response = client.post(
        f"/meetings/{meeting_id}/audio",
        files={"file": ("meeting.wav", b"audio", "audio/wav")},
    )
    assert upload_response.status_code == 201

    TranscriptRepository(db_session).save_transcript(
        meeting_id=meeting_id,
        content="Bom dia. Tudo bem?",
        segments=[
            SegmentData(start=0.0, end=2.0, text="Bom dia."),
            SegmentData(start=2.0, end=4.0, text="Tudo bem?"),
        ],
    )
    return meeting_id


def test_diarize_meeting_assigns_speakers(
    client: TestClient, db_session: Session
) -> None:
    app.dependency_overrides[get_diarization_service] = lambda: DiarizationService(
        FakeDiarizationProvider(
            [
                DiarizationSegment("host", 0.0, 2.0),
                DiarizationSegment("guest", 2.0, 4.0),
            ]
        )
    )
    meeting_id = create_meeting_with_audio_and_transcript(client, db_session)

    response = client.post(f"/meetings/{meeting_id}/diarize")

    assert response.status_code == 200
    assert [segment["speaker"] for segment in response.json()["segments"]] == [
        "SPEAKER_00",
        "SPEAKER_01",
    ]


def test_diarize_meeting_requires_transcript(client: TestClient) -> None:
    meeting_response = client.post("/meetings", json={"title": "Sem transcrição"})
    meeting_id = meeting_response.json()["id"]
    client.post(
        f"/meetings/{meeting_id}/audio",
        files={"file": ("meeting.wav", b"audio", "audio/wav")},
    )

    response = client.post(f"/meetings/{meeting_id}/diarize")

    assert response.status_code == 409
    assert "transcrita" in response.json()["detail"]
