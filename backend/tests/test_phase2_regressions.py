from __future__ import annotations

import io
from datetime import date
from unittest.mock import MagicMock

import pytest
from app.core.config import Settings, settings
from app.core.exceptions import InvalidCredentialsError, InvalidGoogleTokenError
from app.core.security import hash_password
from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.models.user import User
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.summary_repository import SummaryRepository
from app.schemas.summary import SummaryResult
from app.schemas.task import TaskItem as ExtractedTaskItem
from app.services.audio_storage import AudioStorageService
from app.services.auth_service import (
    authenticate_with_credentials,
    change_password,
    verify_google_token,
)
from app.services.chunking import ChunkingService
from app.services.llm.exceptions import LLMConfigurationError
from app.services.processing.meeting_processor import MeetingProcessor
from app.services.transcription.base import SegmentData, TranscriptionResult
from app.workers.meeting_job import build_meeting_processor, run_meeting_processing_job
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_worker_marks_failed_when_llm_unconfigured(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    meeting = Meeting(title="Sem LLM", status=MeetingStatus.PROCESSING)
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    def raise_llm_config():
        raise LLMConfigurationError("Missing required LLM configuration: LLM_API_KEY")

    monkeypatch.setattr("app.services.llm.service.get_llm_service", raise_llm_config)

    non_closing_session = MagicMock(wraps=db_session)
    non_closing_session.close = MagicMock()

    with pytest.raises(LLMConfigurationError, match="LLM_API_KEY"):
        run_meeting_processing_job(
            meeting.id,
            session_factory=lambda: non_closing_session,
        )

    db_session.refresh(meeting)
    assert meeting.status == MeetingStatus.FAILED
    assert meeting.last_error is not None
    assert "LLM_API_KEY" in meeting.last_error


def test_build_meeting_processor_wires_task_extraction_and_saves_freeform_deadlines(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    fake_llm = MagicMock()
    monkeypatch.setattr("app.services.llm.service.get_llm_service", lambda: fake_llm)
    processor = build_meeting_processor(db_session)
    assert processor._task_extraction_service is not None

    meeting = Meeting(title="Extração Tarefas", status=MeetingStatus.AUDIO_UPLOADED)
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    repo = SummaryRepository(db_session)
    summary = repo.save_summary(
        meeting.id,
        objective="Testar schema",
        summary="Resumo geral",
        tasks=[
            ExtractedTaskItem(
                task="Revisar PR #54",
                responsible="Sergio",
                deadline="sexta-feira",
            ),
            ExtractedTaskItem(
                task="Publicar release",
                responsible="Ana",
                deadline="2026-11-30",
            ),
        ],
    )
    assert summary.id is not None
    tasks = repo.list_tasks(meeting.id)
    assert [t.description for t in tasks] == ["Revisar PR #54", "Publicar release"]
    assert tasks[0].deadline is None
    assert tasks[1].deadline == date(2026, 11, 30)


def test_skip_tasks_saves_empty_tasks_list(
    db_session: Session, tmp_path
) -> None:
    storage = AudioStorageService(base_storage_path=tmp_path)
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    meeting = Meeting(title="Skip Tasks", status=MeetingStatus.AUDIO_UPLOADED)
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    from app.models.audio_file import AudioFile

    db_session.add(
        AudioFile(
            meeting_id=meeting.id,
            filename="audio.wav",
            original_filename="audio.wav",
            file_path=str(audio_path),
            file_size_bytes=12,
            content_type="audio/wav",
        )
    )
    db_session.commit()

    stt = MagicMock()
    stt.transcribe.return_value = TranscriptionResult(
        text="Texto da reunião.",
        language="pt",
        duration=2.0,
        segments=[SegmentData(start=0.0, end=2.0, text="Texto da reunião.")],
    )
    summarizer = MagicMock()
    summarizer.summarize.return_value = SummaryResult(
        summary="Resumo",
        tasks=[],
    )
    # Simula summary_result trazendo tarefa no fallback
    summarizer.summarize.return_value = MagicMock(
        objective="Obj",
        summary="Resumo",
        main_points=["P1"],
        decisions=[],
        tasks=[ExtractedTaskItem(task="Não deve ser salva")],
    )

    from app.repositories.transcript_repository import TranscriptRepository

    processor = MeetingProcessor(
        meeting_repository=MeetingRepository(db_session),
        transcript_repository=TranscriptRepository(db_session),
        summary_repository=SummaryRepository(db_session),
        summarization_service=summarizer,
        task_extraction_service=MagicMock(),
        audio_storage_service=storage,
        speech_to_text_service=stt,
        chunking_service=ChunkingService(),
        integration_dispatcher=MagicMock(),
    )
    processor.process_meeting(meeting.id, skip_tasks=True)

    assert SummaryRepository(db_session).list_tasks(meeting.id) == []


def test_export_notion_false_does_not_block_discord_or_obsidian(
    db_session: Session,
) -> None:
    meeting = Meeting(title="Integrações", status=MeetingStatus.PROCESSING)
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    captured_kwargs: dict = {}

    class FakeProcessor:
        def process_meeting(self, meeting_id: int, **kwargs) -> None:
            captured_kwargs["meeting_id"] = meeting_id
            captured_kwargs["kwargs"] = kwargs

    non_closing_session = MagicMock(wraps=db_session)
    non_closing_session.close = MagicMock()

    run_meeting_processing_job(
        meeting.id,
        session_factory=lambda: non_closing_session,
        processor_factory=lambda _s, **_kw: FakeProcessor(),
        options={"export_notion": False},
    )

    assert captured_kwargs["kwargs"].get("skip_integrations") is not True
    assert captured_kwargs["kwargs"].get("excluded_providers") == ["notion"]

    resolved = MeetingProcessor._resolve_integration_providers(
        integration_providers=None,
        excluded_providers=captured_kwargs["kwargs"]["excluded_providers"],
    )
    assert resolved == ["discord", "obsidian"]


def test_processing_options_persisted_and_reused_on_retry(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from app.api.v1.meetings import (
        get_audio_storage_service,
        get_meeting_job_dispatcher,
    )
    from app.main import app

    storage = AudioStorageService(base_storage_path=tmp_path)
    app.dependency_overrides[get_audio_storage_service] = lambda: storage
    dispatched: list[tuple[int, dict | None]] = []

    def fake_dispatcher(meeting_id: int, _bg=None, options=None) -> None:
        dispatched.append((meeting_id, options))

    app.dependency_overrides[get_meeting_job_dispatcher] = lambda: fake_dispatcher
    try:
        mid = client.post("/meetings", json={"title": "Com Opções"}).json()["id"]
        wav_bytes = (
            b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
            b"D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        )
        assert (
            client.post(
                f"/meetings/{mid}/audio",
                files={"file": ("a.wav", io.BytesIO(wav_bytes), "audio/wav")},
            ).status_code
            == 201
        )

        opts = {
            "language": "en",
            "provider": "local",
            "auto_tasks": True,
            "integrations": ["discord", "obsidian"],
        }
        proc_res = client.post(f"/meetings/{mid}/process", json=opts)
        assert proc_res.status_code == 202
        assert dispatched == [(mid, opts)]

        repo = MeetingRepository(db_session)
        meeting = repo.get_by_id(mid)
        assert meeting is not None
        assert meeting.processing_options == opts
        repo.update_status(meeting, MeetingStatus.FAILED)

        retry_calls: list[tuple[int, dict | None]] = []
        monkeypatch.setattr(
            "app.api.v1.meetings.enqueue_meeting_processing",
            lambda m_id, _bg, options=None: retry_calls.append((m_id, options)),
        )
        retry_res = client.post(f"/meetings/{mid}/retry")
        assert retry_res.status_code == 200
        assert retry_calls == [(mid, opts)]
    finally:
        app.dependency_overrides.pop(get_audio_storage_service, None)
        app.dependency_overrides.pop(get_meeting_job_dispatcher, None)


def test_obsidian_enabled_empty_string_is_false() -> None:
    cfg = Settings(
        JWT_SECRET_KEY="test-only-secret-key-with-at-least-32-characters",
        OBSIDIAN_ENABLED="",
        DISCORD_ENABLED="",
        NOTION_ENABLED="",
    )
    assert cfg.obsidian_enabled is False
    assert cfg.discord_enabled is False
    assert cfg.notion_enabled is False


def test_orphan_meetings_without_user_are_isolated(
    db_session: Session, make_auth_client
) -> None:
    orphan = Meeting(title="Órfã sem dono", user_id=None)
    db_session.add(orphan)
    db_session.commit()
    db_session.refresh(orphan)

    alice_client, alice = make_auth_client(email="alice_iso@example.com", name="Alice")
    repo = MeetingRepository(db_session)
    assert repo.get_by_id_and_user(orphan.id, alice.id) is None
    assert all(m.id != orphan.id for m in repo.list_by_user(alice.id))
    assert alice_client.get(f"/meetings/{orphan.id}").status_code == 404
    assert alice_client.get("/meetings").json() == []


def test_verify_google_token_requires_client_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "google_client_id", None)
    called = False

    def fail_if_called(*_args, **_kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(
        "app.services.auth_service.id_token.verify_oauth2_token", fail_if_called
    )

    with pytest.raises(InvalidGoogleTokenError, match="não configurada"):
        verify_google_token("fake-token")
    assert called is False


def test_long_passwords_rejected_before_argon2(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = User(
        email="len@example.com",
        name="Len",
        hashed_password=hash_password("SenhaValida123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    def fail_argon2(*_args, **_kwargs):
        raise AssertionError("Argon2 não deveria ser chamado para senha > 128 chars")

    monkeypatch.setattr("app.services.auth_service.verify_password", fail_argon2)
    monkeypatch.setattr("app.services.auth_service.verify_dummy_password", fail_argon2)

    with pytest.raises(InvalidCredentialsError):
        authenticate_with_credentials(db_session, "len@example.com", "a" * 129)

    with pytest.raises(InvalidCredentialsError):
        change_password(db_session, user, "b" * 129, "NovaSenha123")


def test_users_me_exposes_picture_url_and_has_password(
    db_session: Session, make_auth_client
) -> None:
    pw_client, pw_user = make_auth_client(
        email="pw@example.com", name="Com Senha", password="Password123!"
    )
    pw_user.picture_url = "https://example.com/pw.png"
    db_session.commit()

    res_pw = pw_client.get("/users/me")
    assert res_pw.status_code == 200
    body_pw = res_pw.json()
    assert body_pw["picture_url"] == "https://example.com/pw.png"
    assert body_pw["has_password"] is True

    google_client, _ = make_auth_client(
        email="g_only@example.com",
        name="Google Only",
        password=None,
        google_id="sub-only-google",
    )
    res_g = google_client.get("/users/me")
    assert res_g.status_code == 200
    assert res_g.json()["has_password"] is False
