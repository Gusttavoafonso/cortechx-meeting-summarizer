from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1 import decoder_diagnostics, partial_sessions
from app.core.config import settings
from app.core.database import get_session
from app.core.security import create_access_token
from app.models.partial_session import PartialSession
from app.services.incremental_audio import (
    SAMPLE_RATE,
    STEP_SAMPLES,
    WINDOW_SAMPLES,
    AudioWindow,
    IncrementalWebMDecoder,
)
from app.services.transcription.base import SegmentData, TranscriptionResult
from app.services.transcription.faster_whisper_service import (
    _MODEL_CACHE,
    FasterWhisperService,
)
from app.workers.partial_job import _reconcile


def test_reconcile_deduplicates_overlap_and_normalizes_punctuation():
    prev_tokens = [
        (0.5, "Olá,"),
        (1.5, "pessoal."),
        (3.2, "Vamos"),
        (4.1, "começar!"),
        (5.0, "Agora"),
    ]
    window = AudioWindow(
        samples=np.zeros(WINDOW_SAMPLES, dtype=np.float32),
        start_sample=4 * SAMPLE_RATE,
    )
    result = TranscriptionResult(
        text="agora vamos continuar o projeto",
        segments=[
            SegmentData(start=0.0, end=2.5, text="agora, vamos continuar o projeto"),
        ],
        language="pt",
        duration=6.0,
    )

    merged = _reconcile(prev_tokens, result, window)
    words = [word for _, word in merged]
    assert words == ["Olá,", "pessoal.", "Vamos", "agora,", "vamos", "continuar", "o", "projeto"]

    # Testa match exato na borda com pontuação/caixa diferentes
    prev_tokens_2 = [
        (1.0, "Arquitetura"),
        (2.0, "distribuída."),
        (3.2, "Whisper,"),
        (3.8, "local!"),
    ]
    result_2 = TranscriptionResult(
        text="whisper local com chunks",
        segments=[
            SegmentData(start=0.0, end=3.0, text="whisper local com chunks"),
        ],
        language="pt",
        duration=6.0,
    )
    merged_2 = _reconcile(prev_tokens_2, result_2, window)
    assert [w for _, w in merged_2] == [
        "Arquitetura",
        "distribuída.",
        "Whisper,",
        "local!",
        "com",
        "chunks",
    ]


def test_incremental_decoder_window_constants_and_validation():
    assert SAMPLE_RATE == 16_000
    assert WINDOW_SAMPLES == 6 * SAMPLE_RATE
    assert STEP_SAMPLES == 4 * SAMPLE_RATE
    assert WINDOW_SAMPLES - STEP_SAMPLES == 2 * SAMPLE_RATE

    with pytest.raises(ValueError):
        IncrementalWebMDecoder(max_chunk_bytes=0)
    with pytest.raises(ValueError):
        IncrementalWebMDecoder(max_chunk_bytes=-10)

    decoder = IncrementalWebMDecoder(max_chunk_bytes=2048)
    assert decoder.max_chunk_bytes == 2048


def test_faster_whisper_transcribe_array_uses_expected_params(monkeypatch):
    calls: list[tuple[object, dict]] = []

    class FakeModel:
        def transcribe(self, source, **kwargs):
            calls.append((source, kwargs))
            seg = SimpleNamespace(start=0.1, end=1.2, text=" Olá mundo ")
            info = SimpleNamespace(duration=1.2, language="pt")
            return iter([seg]), info

    cache_key = ("tiny-test", "cpu", "int8")
    _MODEL_CACHE[cache_key] = FakeModel()
    try:
        service = FasterWhisperService(
            model_size="tiny-test",
            device="cpu",
            compute_type="int8",
            vad_filter=True,
        )
        audio = np.zeros(1600, dtype=np.float32)
        result = service.transcribe_array(
            audio,
            language="pt",
            beam_size=1,
            condition_on_previous_text=False,
        )

        assert len(calls) == 1
        passed_source, passed_kwargs = calls[0]
        assert passed_source is audio
        assert passed_kwargs["language"] == "pt"
        assert passed_kwargs["beam_size"] == 1
        assert passed_kwargs["condition_on_previous_text"] is False
        assert passed_kwargs["vad_filter"] is True
        assert result.text == "Olá mundo"
        assert result.segments == [SegmentData(start=0.1, end=1.2, text="Olá mundo")]
    finally:
        _MODEL_CACHE.pop(cache_key, None)


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("POST", "/partial-sessions", {"json": {"provider": "local", "language": "pt"}}),
        (
            "PUT",
            f"/partial-sessions/{uuid4()}/chunks/0",
            {"content": b"\x1a\x45\xdf\xa3payload", "headers": {"Content-Type": "audio/webm"}},
        ),
        ("POST", f"/partial-sessions/{uuid4()}/finish", {"json": {"chunk_count": 1}}),
        ("GET", f"/partial-sessions/{uuid4()}", {}),
        ("DELETE", f"/partial-sessions/{uuid4()}", {}),
    ],
)
def test_partial_sessions_require_authentication(
    anon_client: TestClient, method: str, path: str, kwargs: dict
):
    response = anon_client.request(method, path, **kwargs)
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"

    forged = anon_client.request(
        method,
        path,
        headers={**kwargs.get("headers", {}), "Authorization": "Bearer invalid.token.here"},
        **{k: v for k, v in kwargs.items() if k != "headers"},
    )
    assert forged.status_code == 401


def test_partial_sessions_enforce_ownership_and_accept_cookie_or_bearer(
    db_session: Session,
    make_auth_client,
    anon_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    test_session_local = sessionmaker(
        autocommit=False, autoflush=False, bind=db_session.get_bind()
    )
    monkeypatch.setattr(partial_sessions, "SessionLocal", test_session_local)
    monkeypatch.setattr(partial_sessions.settings, "CELERY_TASK_ALWAYS_EAGER", False)

    alice_client, alice = make_auth_client(email="alice@example.com", name="Alice")
    bob_client, _bob = make_auth_client(email="bob@example.com", name="Bob")

    session_id = str(uuid4())
    db_session.add(
        PartialSession(
            id=session_id,
            user_id=alice.id,
            provider="local",
            language="pt",
            state="completed",
            text="transcrição da alice",
            revision=1,
            processed_seconds=6.0,
        )
    )
    db_session.commit()

    # Dono autenticado via Bearer consegue consultar
    res_bearer = alice_client.get(f"/partial-sessions/{session_id}")
    assert res_bearer.status_code == 200
    assert res_bearer.json()["text"] == "transcrição da alice"

    # Dono autenticado via cookie HTTP-Only também consegue consultar
    alice_token = create_access_token(alice.id)
    res_cookie = anon_client.get(
        f"/partial-sessions/{session_id}",
        cookies={settings.session_cookie_name: alice_token},
    )
    assert res_cookie.status_code == 200
    assert res_cookie.json()["id"] == session_id

    # Outro usuário autenticado não pode acessar, enviar chunk, finalizar, cancelar ou reutilizar o ID
    assert bob_client.get(f"/partial-sessions/{session_id}").status_code == 404
    assert (
        bob_client.put(
            f"/partial-sessions/{session_id}/chunks/0",
            content=b"\x1a\x45\xdf\xa3payload",
            headers={"Content-Type": "audio/webm"},
        ).status_code
        == 404
    )
    assert (
        bob_client.post(
            f"/partial-sessions/{session_id}/finish",
            json={"chunk_count": 1},
        ).status_code
        == 404
    )
    assert bob_client.delete(f"/partial-sessions/{session_id}").status_code == 404
    assert (
        bob_client.post(
            "/partial-sessions",
            json={"id": session_id, "provider": "local", "language": "pt"},
        ).status_code
        == 404
    )


def test_decoder_diagnostics_requires_authentication(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(decoder_diagnostics.settings, "DEBUG", True)

    diag_app = FastAPI()
    diag_app.include_router(decoder_diagnostics.router, prefix="/dev")

    def override_get_session():
        yield db_session

    diag_app.dependency_overrides[get_session] = override_get_session

    with TestClient(diag_app) as diag_client:
        res = diag_client.post(
            "/dev/incremental-audio",
            content=b"ignored",
            headers={"Content-Type": "multipart/form-data; boundary=test"},
        )
        assert res.status_code == 401
        assert res.headers.get("www-authenticate") == "Bearer"
