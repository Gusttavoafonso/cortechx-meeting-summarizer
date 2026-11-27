from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.core.config import DEFAULT_LLM_MODEL, DEFAULT_LLM_PROVIDER, settings
from app.core.failure_recorder import sanitize_error_message
from app.core.secret_crypto import (
    ENCRYPTED_PREFIX,
    SecretDecryptionError,
    decrypt_secret,
    encrypt_secret,
    is_encrypted,
)
from app.integrations.configuration import (
    ProviderConfigurationError,
    ProviderConfigurationResolver,
)
from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.models.user_integration import UserIntegration
from app.services.llm.service import resolve_user_llm_config
from app.workers.meeting_job import build_meeting_processor
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session


def test_integrations_secrets_are_encrypted_at_rest_and_masked_in_api(
    make_auth_client, db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(
        settings, "encryption_key", SecretStr("primary-test-encryption-key-2026")
    )
    alice_client, alice = make_auth_client(email="alice_enc@example.com", name="Alice")

    gemini_key = "AIzaSyAliceSecretKeyForTesting123456789"
    groq_key = "gsk_alice_secret_groq_key_1234567890"
    notion_key = "secret_alice_notion_token_abcdef12345"
    discord_webhook = "https://discord.com/api/webhooks/99887766/alice-secret-hook-tok"

    assert (
        alice_client.put(
            "/settings/integrations/llm",
            json={
                "enabled": True,
                "llm_provider": "gemini",
                "llm_model": "gemini-2.5-pro",
                "api_key": gemini_key,
            },
        ).status_code
        == 200
    )
    assert (
        alice_client.put(
            "/settings/integrations/groq",
            json={"enabled": True, "api_key": groq_key},
        ).status_code
        == 200
    )
    assert (
        alice_client.put(
            "/settings/integrations/notion",
            json={
                "enabled": True,
                "api_key": notion_key,
                "database_id": "22222222-2222-2222-2222-222222222222",
            },
        ).status_code
        == 200
    )
    assert (
        alice_client.put(
            "/settings/integrations/discord",
            json={"enabled": True, "webhook_url": discord_webhook},
        ).status_code
        == 200
    )

    rows = {
        row.provider: row
        for row in db_session.scalars(
            select(UserIntegration).where(UserIntegration.user_id == alice.id)
        ).all()
    }
    assert is_encrypted(rows["llm"].config["api_key"])
    assert gemini_key not in str(rows["llm"].config)

    assert is_encrypted(rows["groq"].config["api_key"])
    assert groq_key not in str(rows["groq"].config)

    assert is_encrypted(rows["notion"].config["api_key"])
    assert notion_key not in str(rows["notion"].config)

    assert is_encrypted(rows["discord"].config["webhook_url"])
    assert "alice-secret-hook-tok" not in str(rows["discord"].config)

    # API retorna apenas valores mascarados, jamais texto puro ou blobs enc:v1:
    res = alice_client.get("/settings/integrations")
    assert res.status_code == 200
    body = res.json()
    raw_text = res.text
    for raw_secret in (gemini_key, groq_key, notion_key, "alice-secret-hook-tok"):
        assert raw_secret not in raw_text
    assert ENCRYPTED_PREFIX not in raw_text

    assert body["llm"]["api_key_masked"] == "AIza...6789"
    assert body["llm"]["llm_model"] == "gemini-2.5-pro"
    assert body["groq"]["api_key_masked"] == "gsk_...7890"
    assert body["notion"]["api_key_masked"] == "secr...2345"
    assert "***masked***" in body["discord"]["webhook_preview"]

    # ProviderConfigurationResolver descriptografa Notion e Discord para Alice
    meeting = Meeting(
        user_id=alice.id,
        title="Crypto Meeting",
        status=MeetingStatus.COMPLETED,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    resolver = ProviderConfigurationResolver(db_session)
    assert resolver.resolve("notion", meeting_id=meeting.id)["api_key"] == notion_key
    assert (
        resolver.resolve("discord", meeting_id=meeting.id)["webhook_url"]
        == discord_webhook
    )


def test_aad_user_and_context_binding_prevents_cross_user_ciphertext_reuse(
    make_auth_client, db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(
        settings, "encryption_key", SecretStr("aad-test-encryption-key-2026")
    )
    alice_client, alice = make_auth_client(email="alice_aad@example.com", name="Alice")
    bob_client, bob = make_auth_client(email="bob_aad@example.com", name="Bob")

    alice_key = "AIzaSyAliceBoundSecretKey1234567890"
    res = alice_client.put(
        "/settings/integrations/llm",
        json={"enabled": True, "llm_provider": "gemini", "api_key": alice_key},
    )
    assert res.status_code == 200

    alice_row = db_session.scalar(
        select(UserIntegration).where(
            UserIntegration.user_id == alice.id,
            UserIntegration.provider == "llm",
        )
    )
    assert alice_row is not None
    alice_ciphertext = alice_row.config["api_key"]

    # Copia maliciosa do ciphertext da Alice para o Bob (e erro de provider/field)
    with pytest.raises(SecretDecryptionError):
        decrypt_secret(
            alice_ciphertext, user_id=bob.id, provider="llm", field="api_key"
        )
    with pytest.raises(SecretDecryptionError):
        decrypt_secret(
            alice_ciphertext, user_id=alice.id, provider="groq", field="api_key"
        )
    with pytest.raises(SecretDecryptionError):
        decrypt_secret(
            alice_ciphertext, user_id=alice.id, provider="llm", field="webhook_url"
        )

    bob_row = UserIntegration(
        user_id=bob.id,
        provider="llm",
        enabled=True,
        config={
            "llm_provider": "gemini",
            "llm_model": "gemini-2.5-flash",
            "api_key": alice_ciphertext,
        },
    )
    db_session.add(bob_row)
    db_session.commit()

    assert resolve_user_llm_config(db_session, bob.id) is None

    bob_settings = bob_client.get("/settings/integrations")
    assert bob_settings.status_code == 200
    assert bob_settings.json()["llm"]["is_configured"] is False
    assert alice_key not in bob_settings.text

    bob_status = bob_client.get("/system/status")
    assert bob_status.status_code == 200
    assert bob_status.json()["llm_source"] != "user"

    # Também testa erro de descriptografia em ProviderConfigurationResolver
    bob_discord = UserIntegration(
        user_id=bob.id,
        provider="discord",
        enabled=True,
        config={"webhook_url": alice_ciphertext},
    )
    bob_meeting = Meeting(
        user_id=bob.id,
        title="Bob Meeting",
        status=MeetingStatus.COMPLETED,
    )
    db_session.add_all([bob_discord, bob_meeting])
    db_session.commit()
    db_session.refresh(bob_meeting)

    resolver = ProviderConfigurationResolver(db_session)
    with pytest.raises(ProviderConfigurationError):
        resolver.resolve("discord", meeting_id=bob_meeting.id)


def test_secret_key_rotation_wrong_key_and_legacy_plaintext_compatibility(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "encryption_key", SecretStr("old-rotation-key-v1"))
    ct_old = encrypt_secret(
        "AIzaSyOldSecretForRotation",
        user_id=7,
        provider="llm",
        field="api_key",
    )
    assert is_encrypted(ct_old)

    # Rotação: nova chave em primeiro lugar + antiga como fallback
    monkeypatch.setattr(
        settings,
        "encryption_key",
        SecretStr("new-rotation-key-v2, old-rotation-key-v1"),
    )
    assert (
        decrypt_secret(ct_old, user_id=7, provider="llm", field="api_key")
        == "AIzaSyOldSecretForRotation"
    )

    # Novas criptografias usam a chave nova ("new-rotation-key-v2")
    ct_new = encrypt_secret(
        "AIzaSyNewSecretAfterRotation",
        user_id=7,
        provider="llm",
        field="api_key",
    )
    monkeypatch.setattr(settings, "encryption_key", SecretStr("new-rotation-key-v2"))
    assert (
        decrypt_secret(ct_new, user_id=7, provider="llm", field="api_key")
        == "AIzaSyNewSecretAfterRotation"
    )

    # Sem a chave antiga no anel, o ciphertext antigo falha
    with pytest.raises(SecretDecryptionError):
        decrypt_secret(ct_old, user_id=7, provider="llm", field="api_key")

    # Registros legados em texto puro continuam legíveis
    assert (
        decrypt_secret(
            "  legacy-plaintext-key  ", user_id=7, provider="llm", field="api_key"
        )
        == "legacy-plaintext-key"
    )


def test_llm_integration_crud_validation_preserve_and_gemini_test(
    make_auth_client, monkeypatch
) -> None:
    monkeypatch.setattr(
        settings, "encryption_key", SecretStr("crud-test-encryption-key")
    )
    monkeypatch.setattr(settings, "llm_provider", None)
    monkeypatch.setattr(settings, "llm_model", None)
    monkeypatch.setattr(settings, "llm_api_key", None)
    client, _user = make_auth_client(email="llm_crud@example.com", name="LLM User")

    # Ativar sem chave deve falhar com 422
    res_missing = client.put(
        "/settings/integrations/llm",
        json={
            "enabled": True,
            "llm_provider": "gemini",
            "llm_model": "gemini-2.5-flash",
        },
    )
    assert res_missing.status_code == 422

    # Salvar chave pessoal
    secret_key = "AIzaSyUserGeminiKeyForCrudTest99"
    res_save = client.put(
        "/settings/integrations/llm",
        json={
            "enabled": True,
            "llm_provider": "gemini",
            "llm_model": "gemini-2.5-pro",
            "api_key": secret_key,
        },
    )
    assert res_save.status_code == 200
    saved = res_save.json()
    assert saved["provider"] == "llm"
    assert saved["enabled"] is True
    assert saved["is_configured"] is True
    assert saved["source"] == "user"
    assert saved["llm_provider"] == "gemini"
    assert saved["llm_model"] == "gemini-2.5-pro"
    assert saved["api_key_masked"] == "AIza...st99"

    # Alternar enabled=False sem reenviar chave preserva api_key
    res_toggle_off = client.put(
        "/settings/integrations/llm",
        json={"enabled": False, "llm_provider": "gemini"},
    )
    assert res_toggle_off.status_code == 200
    assert res_toggle_off.json()["enabled"] is False
    assert res_toggle_off.json()["is_configured"] is True
    assert res_toggle_off.json()["api_key_masked"] == "AIza...st99"
    assert res_toggle_off.json()["llm_model"] == "gemini-2.5-pro"

    # Testar conexão (200, 401, 404) garantindo uso do header x-goog-api-key (sem ?key=)
    captured_calls: list[tuple[str, dict[str, str]]] = []

    def make_fake_get(status_code: int):
        def _fake_get(url: str, *, headers: dict[str, str], timeout: float):
            captured_calls.append((url, dict(headers)))
            return SimpleNamespace(status_code=status_code)

        return _fake_get

    monkeypatch.setattr("app.api.v1.settings.httpx.get", make_fake_get(200))
    res_200 = client.post("/settings/integrations/llm/test")
    assert res_200.status_code == 200
    assert res_200.json()["ok"] is True
    assert len(captured_calls) == 1
    called_url, called_headers = captured_calls[0]
    assert called_url.endswith("/v1beta/models/gemini-2.5-pro")
    assert "key=" not in called_url
    assert secret_key not in called_url
    assert called_headers["x-goog-api-key"] == secret_key

    monkeypatch.setattr("app.api.v1.settings.httpx.get", make_fake_get(401))
    res_401 = client.post("/settings/integrations/llm/test")
    assert res_401.status_code == 200
    assert res_401.json()["ok"] is False
    assert "inválida" in res_401.json()["detail"].lower()

    monkeypatch.setattr("app.api.v1.settings.httpx.get", make_fake_get(404))
    res_404 = client.post("/settings/integrations/llm/test")
    assert res_404.status_code == 200
    assert res_404.json()["ok"] is False
    assert "gemini-2.5-pro" in res_404.json()["detail"]

    # Remover chave pessoal via DELETE
    res_del = client.delete("/settings/integrations/llm")
    assert res_del.status_code == 204
    res_after = client.get("/settings/integrations")
    assert res_after.status_code == 200
    assert res_after.json()["llm"]["source"] == "none"
    assert res_after.json()["llm"]["is_configured"] is False
    assert res_after.json()["llm"]["llm_provider"] == DEFAULT_LLM_PROVIDER
    assert res_after.json()["llm"]["llm_model"] == DEFAULT_LLM_MODEL


def test_build_meeting_processor_and_system_status_use_per_user_llm(
    make_auth_client, anon_client, db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(
        settings, "encryption_key", SecretStr("worker-status-test-key")
    )
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_model", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "llm_api_key", None)

    alice_client, alice = make_auth_client(email="alice_llm@example.com", name="Alice")
    bob_client, bob = make_auth_client(email="bob_llm@example.com", name="Bob")

    alice_key = "AIzaSyAlicePersonalGeminiKey987654"
    res = alice_client.put(
        "/settings/integrations/llm",
        json={
            "enabled": True,
            "llm_provider": "gemini",
            "llm_model": "gemini-2.5-pro",
            "api_key": alice_key,
        },
    )
    assert res.status_code == 200

    # System status: Alice -> user; Bob e anônimo -> none (sem chave no servidor)
    alice_status = alice_client.get("/system/status").json()
    assert alice_status["llm_configured"] is True
    assert alice_status["llm_source"] == "user"
    assert alice_status["llm_provider"] == "gemini"
    assert alice_status["llm_model"] == "gemini-2.5-pro"

    bob_status = bob_client.get("/system/status").json()
    assert bob_status["llm_configured"] is False
    assert bob_status["llm_source"] == "none"

    anon_status = anon_client.get("/system/status").json()
    assert anon_status["llm_configured"] is False
    assert anon_status["llm_source"] == "none"

    # Quando servidor possui chave, Bob cai no servidor enquanto Alice usa a pessoal
    monkeypatch.setattr(
        settings, "llm_api_key", SecretStr("AIzaSyServerFallbackGeminiKey000")
    )
    assert bob_client.get("/system/status").json()["llm_source"] == "server"
    assert alice_client.get("/system/status").json()["llm_source"] == "user"

    # build_meeting_processor resolve chave da Alice e fallback para Bob
    alice_meeting = Meeting(
        user_id=alice.id, title="Alice Meeting", status=MeetingStatus.PROCESSING
    )
    bob_meeting = Meeting(
        user_id=bob.id, title="Bob Meeting", status=MeetingStatus.PROCESSING
    )
    db_session.add_all([alice_meeting, bob_meeting])
    db_session.commit()
    db_session.refresh(alice_meeting)
    db_session.refresh(bob_meeting)

    captured_providers: list[tuple[str, str]] = []

    class FakeGeminiProvider:
        def __init__(self, api_key: str, model: str, retry_policy=None) -> None:
            captured_providers.append((api_key, model))

        def generate(self, prompt: str) -> str:
            return "ok"

    monkeypatch.setattr(
        "app.services.llm.service.GeminiProvider", FakeGeminiProvider
    )
    monkeypatch.setattr(
        "app.workers.meeting_job._get_worker_stt_service",
        lambda *args, **kwargs: MagicMock(),
    )

    build_meeting_processor(db_session, meeting_id=alice_meeting.id)
    build_meeting_processor(db_session, meeting_id=bob_meeting.id)

    assert captured_providers == [
        (alice_key, "gemini-2.5-pro"),
        ("AIzaSyServerFallbackGeminiKey000", "gemini-2.5-flash"),
    ]


def test_sanitize_error_message_redacts_new_secret_and_ciphertext_patterns() -> None:
    raw_msg = (
        "Erro com Gemini AIzaSyShortOrLongKey_12345678, "
        "Anthropic sk-ant-api03-abcdef1234567890, "
        "blob enc:v1:abcDEF1234567890==, "
        "Notion secret_abcdef1234567890 e ntn_1234567890abcdef12, "
        "Discord https://discord.com/api/webhooks/123456789/my-secret-webhook-token"
    )
    cleaned = sanitize_error_message(raw_msg)
    assert "AIzaSyShortOrLongKey_12345678" not in cleaned
    assert "sk-ant-api03-abcdef1234567890" not in cleaned
    assert "abcDEF1234567890==" not in cleaned
    assert "secret_abcdef1234567890" not in cleaned
    assert "ntn_1234567890abcdef12" not in cleaned
    assert "my-secret-webhook-token" not in cleaned
    assert "AIza***[REDACTED]" in cleaned
    assert "sk-ant-***[REDACTED]" in cleaned
    assert "enc:v1:[REDACTED]" in cleaned
    assert "[REDACTED_NOTION_TOKEN]" in cleaned
    assert "[REDACTED_DISCORD_WEBHOOK]" in cleaned


def test_multi_provider_llm_registration_switching_encryption_and_testing(
    make_auth_client, db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(
        settings, "encryption_key", SecretStr("multi-provider-test-key-2026")
    )
    monkeypatch.setattr(settings, "llm_api_key", None)
    client, user = make_auth_client(email="multi_llm@example.com", name="Multi LLM")

    openai_key = "sk-proj-openai-test-secret-key-12345"
    groq_llm_key = "gsk_llm_groq_test_secret_key_67890"
    anthropic_key = "sk-ant-api03-test-secret-key-998877"

    # 1. Cadastra OpenAI
    res_oai = client.put(
        "/settings/integrations/llm",
        json={
            "enabled": True,
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
            "api_key": openai_key,
        },
    )
    assert res_oai.status_code == 200
    body_oai = res_oai.json()
    assert body_oai["llm_provider"] == "openai"
    assert body_oai["llm_model"] == "gpt-4o-mini"
    assert body_oai["api_key_masked"] == "sk-p...2345"
    assert "openai" in body_oai["llm_providers"]

    # 2. Cadastra Groq em paralelo (mantém OpenAI salvo em llm_providers)
    res_groq = client.put(
        "/settings/integrations/llm",
        json={
            "enabled": True,
            "llm_provider": "groq",
            "llm_model": "llama-3.3-70b-versatile",
            "api_key": groq_llm_key,
        },
    )
    assert res_groq.status_code == 200
    body_groq = res_groq.json()
    assert body_groq["llm_provider"] == "groq"
    assert set(body_groq["llm_providers"].keys()) == {"openai", "groq"}

    # 3. Cadastra Anthropic também
    res_ant = client.put(
        "/settings/integrations/llm",
        json={
            "enabled": True,
            "llm_provider": "anthropic",
            "llm_model": "claude-sonnet-4-20250514",
            "api_key": anthropic_key,
        },
    )
    assert res_ant.status_code == 200
    assert set(res_ant.json()["llm_providers"].keys()) == {
        "openai",
        "groq",
        "anthropic",
    }

    # Verifica que todas as chaves no JSON do banco estão criptografadas com enc:v1:
    row = db_session.scalar(
        select(UserIntegration).where(
            UserIntegration.user_id == user.id,
            UserIntegration.provider == "llm",
        )
    )
    assert row is not None
    raw_blob = str(row.config)
    for raw_secret in (openai_key, groq_llm_key, anthropic_key):
        assert raw_secret not in raw_blob
    assert is_encrypted(row.config["api_key"])
    for sub_name in ("openai", "groq", "anthropic"):
        assert is_encrypted(row.config["providers"][sub_name]["api_key"])

    # 4. Alterna ativo para OpenAI sem reenviar chave (usa chave salva do OpenAI)
    res_switch = client.put(
        "/settings/integrations/llm",
        json={"enabled": True, "llm_provider": "openai"},
    )
    assert res_switch.status_code == 200
    assert res_switch.json()["llm_provider"] == "openai"
    assert res_switch.json()["api_key_masked"] == "sk-p...2345"

    # 5. Testa endpoint POST /settings/integrations/llm/test para cada provedor
    seen_calls: list[tuple[str, dict[str, str]]] = []

    def _fake_get(url: str, *, headers: dict[str, str], timeout: float):
        seen_calls.append((url, dict(headers)))
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr("app.api.v1.settings.httpx.get", _fake_get)
    assert client.post("/settings/integrations/llm/test?llm_provider=openai").json()[
        "ok"
    ]
    assert client.post("/settings/integrations/llm/test?llm_provider=groq").json()["ok"]
    assert client.post(
        "/settings/integrations/llm/test?llm_provider=anthropic"
    ).json()["ok"]

    assert seen_calls[0][0] == "https://api.openai.com/v1/models/gpt-4o-mini"
    assert seen_calls[0][1]["Authorization"] == f"Bearer {openai_key}"
    assert (
        seen_calls[1][0]
        == "https://api.groq.com/openai/v1/models/llama-3.3-70b-versatile"
    )
    assert seen_calls[1][1]["Authorization"] == f"Bearer {groq_llm_key}"
    assert (
        seen_calls[2][0]
        == "https://api.anthropic.com/v1/models/claude-sonnet-4-20250514"
    )
    assert seen_calls[2][1]["x-api-key"] == anthropic_key

    # 6. Remoção seletiva de um provedor mantém os outros ativos
    del_oai = client.delete("/settings/integrations/llm?llm_provider=openai")
    assert del_oai.status_code == 204
    after_del = client.get("/settings/integrations").json()["llm"]
    assert set(after_del["llm_providers"].keys()) == {"groq", "anthropic"}
    assert after_del["llm_provider"] in {"groq", "anthropic"}

    # 7. Worker build_meeting_processor instancia o provedor ativo do usuário
    captured_oai: list[tuple[str, str, str]] = []

    class FakeOpenAICompat:
        def __init__(
            self,
            api_key: str,
            model: str,
            *,
            provider_name: str = "openai",
            base_url: str | None = None,
            retry_policy=None,
        ) -> None:
            captured_oai.append((provider_name, api_key, model))

        def generate(self, prompt: str) -> str:
            return "ok"

    client.put(
        "/settings/integrations/llm",
        json={"enabled": True, "llm_provider": "groq"},
    )
    meeting = Meeting(
        user_id=user.id, title="Groq LLM Meeting", status=MeetingStatus.PROCESSING
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    monkeypatch.setattr(
        "app.services.llm.service.OpenAICompatibleProvider", FakeOpenAICompat
    )
    monkeypatch.setattr(
        "app.workers.meeting_job._get_worker_stt_service",
        lambda *args, **kwargs: MagicMock(),
    )
    build_meeting_processor(db_session, meeting_id=meeting.id)
    assert captured_oai == [("groq", groq_llm_key, "llama-3.3-70b-versatile")]
