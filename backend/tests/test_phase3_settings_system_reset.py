from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.core.config import settings
from app.integrations.configuration import (
    ProviderConfigurationResolver,
    ProviderDisabledError,
)
from app.integrations.delivery import IntegrationDeliveryService
from app.models.integration_configuration import IntegrationConfiguration
from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.models.password_reset_token import PasswordResetToken
from app.models.summary import Summary
from app.models.user_integration import UserIntegration
from app.repositories.integration_delivery_repository import (
    IntegrationDeliveryRepository,
)
from app.repositories.meeting_repository import MeetingRepository
from app.schemas.integration import IntegrationResult
from app.services.transcription.faster_whisper_service import FasterWhisperService
from app.services.transcription.groq_whisper_service import GroqWhisperService
from app.workers.meeting_job import build_meeting_processor
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_settings_integrations_crud_masks_secrets_and_validates_obsidian(
    make_auth_client, tmp_path
) -> None:
    alice_client, _alice = make_auth_client(email="alice_s@example.com", name="Alice")
    bob_client, _bob = make_auth_client(email="bob_s@example.com", name="Bob")

    res_init = alice_client.get("/settings/integrations")
    assert res_init.status_code == 200
    body_init = res_init.json()
    assert set(body_init.keys()) == {"discord", "notion", "obsidian", "groq"}

    # Discord PUT + máscara
    res_disc = alice_client.put(
        "/settings/integrations/discord",
        json={
            "enabled": True,
            "webhook_url": "https://discord.com/api/webhooks/123456/super-secret-token",
        },
    )
    assert res_disc.status_code == 200
    disc_data = res_disc.json()
    assert disc_data["enabled"] is True
    assert disc_data["is_configured"] is True
    assert disc_data["source"] == "user"
    assert "super-secret-token" not in disc_data["webhook_preview"]
    assert "***masked***" in disc_data["webhook_preview"]

    # Toggle disabled sem reenviar webhook preserva o segredo salvo
    res_disc_off = alice_client.put(
        "/settings/integrations/discord",
        json={"enabled": False},
    )
    assert res_disc_off.status_code == 200
    assert res_disc_off.json()["enabled"] is False
    assert res_disc_off.json()["is_configured"] is True

    # Notion PUT
    res_notion = alice_client.put(
        "/settings/integrations/notion",
        json={
            "enabled": True,
            "api_key": "secret_1234567890abcdef",
            "database_id": "11111111-1111-1111-1111-111111111111",
        },
    )
    assert res_notion.status_code == 200
    assert res_notion.json()["api_key_masked"] == "secr...cdef"
    assert "secret_1234567890abcdef" not in res_notion.text

    # Obsidian traversal rejeitado
    res_obs_bad = alice_client.put(
        "/settings/integrations/obsidian",
        json={"enabled": True, "vault_path": str(tmp_path), "notes_folder": "../fora"},
    )
    assert res_obs_bad.status_code == 422

    res_obs_abs = alice_client.put(
        "/settings/integrations/obsidian",
        json={"enabled": True, "vault_path": str(tmp_path), "notes_folder": "/etc"},
    )
    assert res_obs_abs.status_code == 422

    # Obsidian válido
    res_obs_ok = alice_client.put(
        "/settings/integrations/obsidian",
        json={
            "enabled": True,
            "vault_path": str(tmp_path),
            "notes_folder": "Reuniões",
        },
    )
    assert res_obs_ok.status_code == 200
    assert res_obs_ok.json()["vault_path"] == str(tmp_path)

    # Groq PUT
    res_groq = alice_client.put(
        "/settings/integrations/groq",
        json={"enabled": True, "api_key": "gsk_my_personal_groq_key_1234"},
    )
    assert res_groq.status_code == 200
    assert res_groq.json()["api_key_masked"] == "gsk_...1234"
    assert "gsk_my_personal_groq_key_1234" not in res_groq.text

    # Isolamento: Bob não vê configurações da Alice
    bob_get = bob_client.get("/settings/integrations").json()
    assert bob_get["groq"]["source"] != "user"

    # DELETE remove a configuração do usuário
    del_res = alice_client.delete("/settings/integrations/groq")
    assert del_res.status_code == 204
    after_del = alice_client.get("/settings/integrations").json()
    assert after_del["groq"]["source"] != "user"


def test_settings_integrations_test_endpoints(
    make_auth_client, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    alice_client, _ = make_auth_client(email="tester@example.com", name="Tester")

    # Discord test
    alice_client.put(
        "/settings/integrations/discord",
        json={
            "enabled": True,
            "webhook_url": "https://discord.com/api/webhooks/123/abc",
        },
    )
    monkeypatch.setattr(
        "app.api.v1.settings.httpx.post",
        lambda *_a, **_kw: SimpleNamespace(status_code=204),
    )
    assert alice_client.post("/settings/integrations/discord/test").json()["ok"] is True

    # Obsidian test
    vault = tmp_path / "vault"
    vault.mkdir()
    alice_client.put(
        "/settings/integrations/obsidian",
        json={"enabled": True, "vault_path": str(vault), "notes_folder": "Meetings"},
    )
    obs_test = alice_client.post("/settings/integrations/obsidian/test").json()
    assert obs_test["ok"] is True
    assert (vault / "Meetings").is_dir()

    # Notion test (data_sources primeiro, com fallback em 404/AttributeError)
    alice_client.put(
        "/settings/integrations/notion",
        json={
            "enabled": True,
            "api_key": "secret_notion_123456",
            "database_id": "11111111-1111-1111-1111-111111111111",
        },
    )
    fake_notion = MagicMock()
    monkeypatch.setattr(
        "app.api.v1.settings.NotionClient", lambda auth: fake_notion
    )
    assert alice_client.post("/settings/integrations/notion/test").json()["ok"] is True
    fake_notion.data_sources.retrieve.assert_called_once_with(
        data_source_id="11111111-1111-1111-1111-111111111111"
    )
    fake_notion.databases.retrieve.assert_not_called()

    # Fallback para databases.retrieve quando data_sources retorna 404 ou AttributeError
    from notion_client.errors import APIResponseError

    fake_notion.data_sources.retrieve.side_effect = APIResponseError(
        "object_not_found",
        404,
        "Not found",
        {},
        "{}",
    )
    assert alice_client.post("/settings/integrations/notion/test").json()["ok"] is True
    fake_notion.databases.retrieve.assert_called_once_with(
        database_id="11111111-1111-1111-1111-111111111111"
    )

    fake_notion.databases.retrieve.reset_mock()
    fake_notion.data_sources.retrieve.side_effect = AttributeError("no data_sources")
    assert alice_client.post("/settings/integrations/notion/test").json()["ok"] is True
    fake_notion.databases.retrieve.assert_called_once_with(
        database_id="11111111-1111-1111-1111-111111111111"
    )

    # Groq test
    alice_client.put(
        "/settings/integrations/groq",
        json={"enabled": True, "api_key": "gsk_valid_key_1234567890"},
    )
    monkeypatch.setattr(
        "app.api.v1.settings.httpx.get",
        lambda *_a, **_kw: SimpleNamespace(status_code=200),
    )
    assert alice_client.post("/settings/integrations/groq/test").json()["ok"] is True


def test_user_integration_precedence_and_delivery_integration(
    db_session: Session, make_auth_client
) -> None:
    _, alice = make_auth_client(email="alice_int@example.com", name="Alice")
    meeting = Meeting(
        title="Com UserIntegration",
        user_id=alice.id,
        status=MeetingStatus.COMPLETED,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)
    db_session.add(Summary(meeting_id=meeting.id, summary="Resumo"))
    db_session.commit()

    user_discord = UserIntegration(
        user_id=alice.id,
        provider="discord",
        enabled=True,
        config={"webhook_url": "https://discord.com/api/webhooks/u/tok"},
    )
    db_session.add(user_discord)
    db_session.commit()

    resolver = ProviderConfigurationResolver(db_session)
    resolved = resolver.resolve("discord", meeting_id=meeting.id)
    assert resolved["webhook_url"] == "https://discord.com/api/webhooks/u/tok"

    # IntegrationConfiguration da reunião sobrepõe UserIntegration
    db_session.add(
        IntegrationConfiguration(
            meeting_id=meeting.id,
            platform="discord",
            enabled=True,
            configuration={"webhook_url": "https://discord.com/api/webhooks/m/tok"},
        )
    )
    db_session.commit()
    assert (
        resolver.resolve("discord", meeting_id=meeting.id)["webhook_url"]
        == "https://discord.com/api/webhooks/m/tok"
    )

    # Desabilitação no usuário bloqueia quando não há override da reunião
    meeting2 = Meeting(
        title="Disabled user",
        user_id=alice.id,
        status=MeetingStatus.COMPLETED,
    )
    db_session.add(meeting2)
    db_session.commit()
    user_discord.enabled = False
    db_session.commit()
    with pytest.raises(ProviderDisabledError):
        resolver.resolve("discord", meeting_id=meeting2.id)

    # Reabilitando no usuário torna provider elegível mesmo com .env false
    user_discord.enabled = True
    db_session.commit()
    sender = MagicMock()
    sender.send_persisted_meeting.return_value = IntegrationResult(
        provider="discord", success=True, metadata={"external_id": "ok"}
    )
    delivery = IntegrationDeliveryService(
        meeting_repository=MeetingRepository(db_session),
        delivery_repository=IntegrationDeliveryRepository(db_session),
        integration_service=sender,
        configuration_resolver=resolver,
    )
    report = delivery.deliver(meeting.id)
    assert [o.provider for o in report.outcomes] == ["discord"]
    assert report.outcomes[0].status == "success"


def test_worker_stt_uses_user_groq_key_unless_local_forced(
    db_session: Session, make_auth_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, alice = make_auth_client(email="alice_stt@example.com", name="Alice")
    db_session.add(
        UserIntegration(
            user_id=alice.id,
            provider="groq",
            enabled=True,
            config={"api_key": "gsk_user_stt_key_123456"},
        )
    )
    meeting = Meeting(title="STT", user_id=alice.id, status=MeetingStatus.PROCESSING)
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    monkeypatch.setattr("app.services.llm.service.get_llm_service", lambda: MagicMock())

    proc_auto = build_meeting_processor(
        db_session, options={"provider": "auto"}, meeting_id=meeting.id
    )
    assert isinstance(proc_auto._speech_to_text_service, GroqWhisperService)
    assert proc_auto._speech_to_text_service.api_key == "gsk_user_stt_key_123456"

    proc_local = build_meeting_processor(
        db_session, options={"provider": "local"}, meeting_id=meeting.id
    )
    assert isinstance(proc_local._speech_to_text_service, FasterWhisperService)


def test_system_status_reflects_user_groq_server_groq_or_local(
    anon_client: TestClient,
    make_auth_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "groq_api_key", None)
    res_anon = anon_client.get("/system/status")
    assert res_anon.status_code == 200
    assert res_anon.json()["stt_mode"] == "local"
    assert res_anon.json()["stt_source"] == "local"

    alice_client, _ = make_auth_client(email="alice_sys@example.com", name="Alice")
    alice_client.put(
        "/settings/integrations/groq",
        json={"enabled": True, "api_key": "gsk_sys_user_key_123456"},
    )
    res_user = alice_client.get("/system/status")
    assert res_user.status_code == 200
    assert res_user.json()["stt_mode"] == "groq"
    assert res_user.json()["stt_source"] == "user"


def test_forgot_and_reset_password_flow(
    anon_client: TestClient,
    db_session: Session,
    make_auth_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, user = make_auth_client(
        email="resetme@example.com", name="Reset", password="OldPassword123!"
    )

    # Em produção (DEBUG=False) nunca vaza reset_token
    monkeypatch.setattr(settings, "DEBUG", False)
    res_prod = anon_client.post(
        "/auth/forgot-password", json={"email": "resetme@example.com"}
    )
    assert res_prod.status_code == 200
    assert res_prod.json()["reset_token"] is None

    # Em DEBUG=True retorna token para fluxo local
    monkeypatch.setattr(settings, "DEBUG", True)
    res_dbg = anon_client.post(
        "/auth/forgot-password", json={"email": "resetme@example.com"}
    )
    assert res_dbg.status_code == 200
    token = res_dbg.json()["reset_token"]
    assert token is not None

    # Conta apenas Google retorna resposta uniforme sem token
    make_auth_client(
        email="google_only_reset@example.com",
        name="Google",
        password=None,
        google_id="sub-reset-google",
    )
    res_google = anon_client.post(
        "/auth/forgot-password", json={"email": "google_only_reset@example.com"}
    )
    assert res_google.status_code == 200
    assert res_google.json()["reset_token"] is None

    # Reset com token válido
    res_reset = anon_client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "NewPassword456!"},
    )
    assert res_reset.status_code == 200

    # Reuso do mesmo token falha
    res_reuse = anon_client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "AnotherPassword789!"},
    )
    assert res_reuse.status_code == 400

    # Login com nova senha funciona
    login_res = anon_client.post(
        "/auth/login",
        data={"username": "resetme@example.com", "password": "NewPassword456!"},
    )
    assert login_res.status_code == 200

    # Token expirado é rejeitado
    expired_raw = "expired-token-value-1234567890"
    db_session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(expired_raw.encode("utf-8")).hexdigest(),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
    )
    db_session.commit()
    res_exp = anon_client.post(
        "/auth/reset-password",
        json={"token": expired_raw, "new_password": "ValidPassword999!"},
    )
    assert res_exp.status_code == 400
