from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from notion_client import Client as NotionClient
from notion_client.errors import APIResponseError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import (
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_MODELS,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_OBSIDIAN_NOTES_FOLDER,
    SUPPORTED_LLM_PROVIDERS,
    settings,
)
from app.core.database import get_session
from app.core.secret_crypto import (
    SecretDecryptionError,
    decrypt_config_secrets,
    encrypt_config_secrets,
)
from app.integrations.providers.discord import _mask_webhook_url
from app.models.user import User
from app.models.user_integration import UserIntegration
from app.schemas.settings import (
    DiscordIntegrationUpdate,
    GroqIntegrationUpdate,
    IntegrationsSettingsResponse,
    IntegrationStatusItem,
    IntegrationTestResponse,
    LLMIntegrationUpdate,
    LLMProviderItem,
    NotionIntegrationUpdate,
    ObsidianIntegrationUpdate,
    ProviderName,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])

ALLOWED_PROVIDERS: set[str] = {"discord", "notion", "obsidian", "groq", "llm"}
_LLM_MODEL_RE = re.compile(r"^[a-zA-Z0-9._-]+(?:/[a-zA-Z0-9._-]+)*$")


def _mask_secret(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    clean = value.strip()
    if len(clean) <= 8:
        return "****"
    return f"{clean[:4]}...{clean[-4:]}"


def _secret_value(secret: Any) -> str | None:
    if secret is None:
        return None
    if hasattr(secret, "get_secret_value"):
        val = secret.get_secret_value()
    else:
        val = str(secret)
    cleaned = val.strip()
    return cleaned or None


def _get_user_integration(
    db: Session, user_id: int, provider: str
) -> UserIntegration | None:
    return db.scalar(
        select(UserIntegration).where(
            UserIntegration.user_id == user_id,
            UserIntegration.provider == provider,
        )
    )


def _read_decrypted_config(row: UserIntegration | None) -> dict[str, Any]:
    if row is None or not isinstance(row.config, dict):
        return {}
    try:
        return decrypt_config_secrets(
            dict(row.config),
            user_id=row.user_id,
            provider=row.provider,
        )
    except SecretDecryptionError:
        logger.warning(
            "Falha ao descriptografar configuração '%s' do usuário %s.",
            row.provider,
            row.user_id,
        )
        return {}


def _extract_llm_providers_map(cfg: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Extrai o mapa {provider: {llm_model, api_key}} mantendo legado compatível."""
    providers_map: dict[str, dict[str, str]] = {}
    raw_providers = cfg.get("providers")
    if isinstance(raw_providers, dict):
        for sub_name, sub_cfg in raw_providers.items():
            if not isinstance(sub_cfg, dict):
                continue
            sub_key = str(sub_name).strip().lower()
            if sub_key not in SUPPORTED_LLM_PROVIDERS:
                continue
            entry: dict[str, str] = {}
            model_val = sub_cfg.get("llm_model")
            key_val = sub_cfg.get("api_key")
            if isinstance(model_val, str) and model_val.strip():
                entry["llm_model"] = model_val.strip()
            if isinstance(key_val, str) and key_val.strip():
                entry["api_key"] = key_val.strip()
            if entry:
                providers_map[sub_key] = entry

    active_provider = str(cfg.get("llm_provider") or "").strip().lower()
    if active_provider in SUPPORTED_LLM_PROVIDERS:
        entry = dict(providers_map.get(active_provider, {}))
        active_model = cfg.get("llm_model")
        active_key = cfg.get("api_key")
        if (
            "llm_model" not in entry
            and isinstance(active_model, str)
            and active_model.strip()
        ):
            entry["llm_model"] = active_model.strip()
        if (
            "api_key" not in entry
            and isinstance(active_key, str)
            and active_key.strip()
        ):
            entry["api_key"] = active_key.strip()
        if entry:
            providers_map[active_provider] = entry

    return providers_map


def _upsert_user_integration(
    db: Session,
    user_id: int,
    provider: str,
    *,
    enabled: bool,
    config: dict[str, Any],
) -> UserIntegration:
    encrypted_config = encrypt_config_secrets(
        config,
        user_id=user_id,
        provider=provider,
    )
    row = _get_user_integration(db, user_id, provider)
    if row is None:
        row = UserIntegration(
            user_id=user_id,
            provider=provider,
            enabled=enabled,
            config=encrypted_config,
        )
        db.add(row)
    else:
        row.enabled = enabled
        row.config = encrypted_config
    db.commit()
    db.refresh(row)
    return row


def _build_status_item(
    provider: ProviderName,
    row: UserIntegration | None,
) -> IntegrationStatusItem:
    cfg = _read_decrypted_config(row)

    if provider == "discord":
        if row is not None:
            url = cfg.get("webhook_url") or _secret_value(
                str(settings.discord_webhook_url)
                if settings.discord_webhook_url
                else None
            )
            return IntegrationStatusItem(
                provider="discord",
                enabled=row.enabled,
                is_configured=bool(url),
                source="user",
                webhook_preview=_mask_webhook_url(url) if url else None,
            )
        env_url = (
            str(settings.discord_webhook_url)
            if settings.discord_webhook_url
            else None
        )
        return IntegrationStatusItem(
            provider="discord",
            enabled=bool(settings.discord_enabled),
            is_configured=bool(env_url),
            source="env" if (settings.discord_enabled or env_url) else "none",
            webhook_preview=_mask_webhook_url(env_url) if env_url else None,
        )

    if provider == "notion":
        if row is not None:
            api_key = cfg.get("api_key") or _secret_value(settings.notion_token)
            db_id = cfg.get("database_id") or settings.notion_database_id
            return IntegrationStatusItem(
                provider="notion",
                enabled=row.enabled,
                is_configured=bool(api_key and db_id),
                source="user",
                api_key_masked=_mask_secret(api_key),
                database_id=db_id,
            )
        env_key = _secret_value(settings.notion_token)
        env_db = settings.notion_database_id
        return IntegrationStatusItem(
            provider="notion",
            enabled=bool(settings.notion_enabled),
            is_configured=bool(env_key and env_db),
            source="env"
            if (settings.notion_enabled or env_key or env_db)
            else "none",
            api_key_masked=_mask_secret(env_key),
            database_id=env_db,
        )

    if provider == "obsidian":
        if row is not None:
            vault = cfg.get("vault_path") or (
                str(settings.obsidian_vault_path)
                if settings.obsidian_vault_path
                else None
            )
            folder = cfg.get("notes_folder") or settings.obsidian_notes_folder
            return IntegrationStatusItem(
                provider="obsidian",
                enabled=row.enabled,
                is_configured=bool(vault),
                source="user",
                vault_path=vault,
                notes_folder=folder,
            )
        env_vault = (
            str(settings.obsidian_vault_path)
            if settings.obsidian_vault_path
            else None
        )
        return IntegrationStatusItem(
            provider="obsidian",
            enabled=bool(settings.obsidian_enabled),
            is_configured=bool(env_vault),
            source="env"
            if (settings.obsidian_enabled or env_vault)
            else "none",
            vault_path=env_vault,
            notes_folder=settings.obsidian_notes_folder,
        )

    if provider == "llm":
        if row is not None:
            providers_map = _extract_llm_providers_map(cfg)
            llm_provider = (
                str(cfg.get("llm_provider") or DEFAULT_LLM_PROVIDER).strip().lower()
            )
            sub_cfg = providers_map.get(llm_provider, {})
            api_key = cfg.get("api_key") or sub_cfg.get("api_key")
            default_for_provider = DEFAULT_LLM_MODELS.get(
                llm_provider, settings.llm_model or DEFAULT_LLM_MODEL
            )
            llm_model = (
                cfg.get("llm_model") or sub_cfg.get("llm_model") or default_for_provider
            )
            llm_providers = {
                sub: LLMProviderItem(
                    llm_provider=sub,  # type: ignore[arg-type]
                    llm_model=item.get("llm_model")
                    or DEFAULT_LLM_MODELS.get(sub, DEFAULT_LLM_MODEL),
                    api_key_masked=_mask_secret(item.get("api_key")),
                    is_configured=bool(item.get("api_key")),
                )
                for sub, item in providers_map.items()
                if item.get("api_key")
            }
            return IntegrationStatusItem(
                provider="llm",
                enabled=row.enabled,
                is_configured=bool(api_key),
                source="user",
                api_key_masked=_mask_secret(api_key),
                llm_provider=llm_provider,
                llm_model=llm_model,
                llm_providers=llm_providers or None,
            )
        env_key = _secret_value(settings.llm_api_key)
        has_env = bool(settings.llm_provider and settings.llm_model and env_key)
        return IntegrationStatusItem(
            provider="llm",
            enabled=has_env,
            is_configured=has_env,
            source="env" if has_env else "none",
            api_key_masked=_mask_secret(env_key) if has_env else None,
            llm_provider=settings.llm_provider or DEFAULT_LLM_PROVIDER,
            llm_model=settings.llm_model or DEFAULT_LLM_MODEL,
            llm_providers=None,
        )

    # groq
    if row is not None:
        api_key = cfg.get("api_key")
        return IntegrationStatusItem(
            provider="groq",
            enabled=row.enabled,
            is_configured=bool(api_key),
            source="user",
            api_key_masked=_mask_secret(api_key),
        )
    env_groq = _secret_value(settings.groq_api_key)
    return IntegrationStatusItem(
        provider="groq",
        enabled=bool(env_groq),
        is_configured=bool(env_groq),
        source="env" if env_groq else "none",
        api_key_masked=_mask_secret(env_groq),
    )


@router.get(
    "/integrations",
    response_model=IntegrationsSettingsResponse,
    summary="Listar estado das integrações do usuário",
)
def get_integrations_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> IntegrationsSettingsResponse:
    rows = {
        row.provider: row
        for row in db.scalars(
            select(UserIntegration).where(UserIntegration.user_id == current_user.id)
        ).all()
    }
    return IntegrationsSettingsResponse(
        discord=_build_status_item("discord", rows.get("discord")),
        notion=_build_status_item("notion", rows.get("notion")),
        obsidian=_build_status_item("obsidian", rows.get("obsidian")),
        groq=_build_status_item("groq", rows.get("groq")),
        llm=_build_status_item("llm", rows.get("llm")),
    )


@router.put(
    "/integrations/discord",
    response_model=IntegrationStatusItem,
    summary="Salvar configuração do Discord do usuário",
)
def update_discord_integration(
    payload: DiscordIntegrationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> IntegrationStatusItem:
    existing = _get_user_integration(db, current_user.id, "discord")
    existing_cfg = _read_decrypted_config(existing)
    webhook_url = payload.webhook_url or existing_cfg.get("webhook_url")

    env_url = (
        str(settings.discord_webhook_url) if settings.discord_webhook_url else None
    )
    if payload.enabled and not (webhook_url or env_url):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Informe a URL do webhook do Discord para ativar a integração.",
        )

    new_cfg: dict[str, Any] = {}
    if webhook_url:
        new_cfg["webhook_url"] = webhook_url
    row = _upsert_user_integration(
        db, current_user.id, "discord", enabled=payload.enabled, config=new_cfg
    )
    return _build_status_item("discord", row)


@router.put(
    "/integrations/notion",
    response_model=IntegrationStatusItem,
    summary="Salvar configuração do Notion do usuário",
)
def update_notion_integration(
    payload: NotionIntegrationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> IntegrationStatusItem:
    existing = _get_user_integration(db, current_user.id, "notion")
    existing_cfg = _read_decrypted_config(existing)

    api_key = payload.api_key or existing_cfg.get("api_key")
    database_id = payload.database_id or existing_cfg.get("database_id")

    eff_key = api_key or _secret_value(settings.notion_token)
    eff_db = database_id or settings.notion_database_id
    if payload.enabled and not (eff_key and eff_db):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Informe Token e Database ID do Notion para ativar a integração.",
        )

    new_cfg: dict[str, Any] = {}
    if api_key:
        new_cfg["api_key"] = api_key
    if database_id:
        new_cfg["database_id"] = database_id
    row = _upsert_user_integration(
        db, current_user.id, "notion", enabled=payload.enabled, config=new_cfg
    )
    return _build_status_item("notion", row)


@router.put(
    "/integrations/obsidian",
    response_model=IntegrationStatusItem,
    summary="Salvar configuração do Obsidian do usuário",
)
def update_obsidian_integration(
    payload: ObsidianIntegrationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> IntegrationStatusItem:
    existing = _get_user_integration(db, current_user.id, "obsidian")
    existing_cfg = _read_decrypted_config(existing)

    vault_path = payload.vault_path or existing_cfg.get("vault_path")
    notes_folder = (
        payload.notes_folder
        or existing_cfg.get("notes_folder")
        or DEFAULT_OBSIDIAN_NOTES_FOLDER
    )

    eff_vault = vault_path or (
        str(settings.obsidian_vault_path) if settings.obsidian_vault_path else None
    )
    if payload.enabled and not eff_vault:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Informe o caminho do vault do Obsidian para ativar a integração.",
        )

    new_cfg: dict[str, Any] = {"notes_folder": notes_folder}
    if vault_path:
        new_cfg["vault_path"] = vault_path
    row = _upsert_user_integration(
        db, current_user.id, "obsidian", enabled=payload.enabled, config=new_cfg
    )
    return _build_status_item("obsidian", row)


@router.put(
    "/integrations/groq",
    response_model=IntegrationStatusItem,
    summary="Salvar chave opcional da Groq para transcrição",
)
def update_groq_integration(
    payload: GroqIntegrationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> IntegrationStatusItem:
    existing = _get_user_integration(db, current_user.id, "groq")
    existing_cfg = _read_decrypted_config(existing)
    api_key = payload.api_key or existing_cfg.get("api_key")

    if payload.enabled and not api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Informe sua chave da API Groq para ativar o STT em nuvem.",
        )

    new_cfg: dict[str, Any] = {}
    if api_key:
        new_cfg["api_key"] = api_key
    row = _upsert_user_integration(
        db, current_user.id, "groq", enabled=payload.enabled, config=new_cfg
    )
    return _build_status_item("groq", row)


@router.put(
    "/integrations/llm",
    response_model=IntegrationStatusItem,
    summary="Salvar chave pessoal de LLM para sumarização",
)
def update_llm_integration(
    payload: LLMIntegrationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> IntegrationStatusItem:
    existing = _get_user_integration(db, current_user.id, "llm")
    existing_cfg = _read_decrypted_config(existing)
    providers_map = _extract_llm_providers_map(existing_cfg)
    sub = payload.llm_provider
    sub_existing = providers_map.get(sub, {})

    api_key = payload.api_key or sub_existing.get("api_key")
    default_model = DEFAULT_LLM_MODELS.get(sub, DEFAULT_LLM_MODEL)
    model_to_save = (
        payload.llm_model
        or sub_existing.get("llm_model")
        or (
            settings.llm_model
            if sub == (settings.llm_provider or DEFAULT_LLM_PROVIDER).strip().lower()
            and settings.llm_model
            else None
        )
        or default_model
    )

    if payload.enabled and not api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Informe sua chave de API do provedor LLM para ativar "
                "a sumarização pessoal."
            ),
        )

    sub_entry: dict[str, str] = {"llm_model": model_to_save}
    if api_key:
        sub_entry["api_key"] = api_key
    providers_map[sub] = sub_entry

    new_cfg: dict[str, Any] = {
        "llm_provider": sub,
        "llm_model": model_to_save,
        "providers": providers_map,
    }
    if api_key:
        new_cfg["api_key"] = api_key
    row = _upsert_user_integration(
        db, current_user.id, "llm", enabled=payload.enabled, config=new_cfg
    )
    return _build_status_item("llm", row)


@router.delete(
    "/integrations/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Remover configuração pessoal de uma integração",
)
def delete_integration(
    provider: str,
    llm_provider: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> Response:
    provider_name = provider.strip().lower()
    if provider_name not in ALLOWED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider desconhecido: {provider}.",
        )
    row = _get_user_integration(db, current_user.id, provider_name)
    if row is not None:
        if provider_name == "llm" and llm_provider and llm_provider.strip():
            sub = llm_provider.strip().lower()
            if sub not in SUPPORTED_LLM_PROVIDERS:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Provedor LLM desconhecido: {llm_provider}.",
                )
            cfg = _read_decrypted_config(row)
            providers_map = _extract_llm_providers_map(cfg)
            providers_map.pop(sub, None)
            remaining = {
                k: v for k, v in providers_map.items() if v.get("api_key")
            }
            if not remaining:
                db.delete(row)
                db.commit()
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            active = str(cfg.get("llm_provider") or "").strip().lower()
            if active not in remaining:
                active = next(iter(remaining))
            active_entry = remaining[active]
            new_cfg: dict[str, Any] = {
                "llm_provider": active,
                "llm_model": active_entry.get("llm_model")
                or DEFAULT_LLM_MODELS.get(active, DEFAULT_LLM_MODEL),
                "api_key": active_entry["api_key"],
                "providers": remaining,
            }
            _upsert_user_integration(
                db, current_user.id, "llm", enabled=row.enabled, config=new_cfg
            )
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        db.delete(row)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/integrations/{provider}/test",
    response_model=IntegrationTestResponse,
    summary="Validar e testar a configuração de uma integração",
)
def test_integration(
    provider: str,
    llm_provider: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> IntegrationTestResponse:
    provider_name = provider.strip().lower()
    if provider_name not in ALLOWED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider desconhecido: {provider}.",
        )

    row = _get_user_integration(db, current_user.id, provider_name)
    cfg = _read_decrypted_config(row)

    if provider_name == "discord":
        return _test_discord(
            cfg.get("webhook_url")
            or (
                str(settings.discord_webhook_url)
                if settings.discord_webhook_url
                else None
            )
        )
    if provider_name == "notion":
        return _test_notion(
            cfg.get("api_key") or _secret_value(settings.notion_token),
            cfg.get("database_id") or settings.notion_database_id,
        )
    if provider_name == "obsidian":
        return _test_obsidian(
            cfg.get("vault_path")
            or (
                str(settings.obsidian_vault_path)
                if settings.obsidian_vault_path
                else None
            ),
            cfg.get("notes_folder") or settings.obsidian_notes_folder,
        )
    if provider_name == "llm":
        providers_map = _extract_llm_providers_map(cfg)
        target_provider = (
            llm_provider.strip().lower()
            if llm_provider and llm_provider.strip()
            else str(
                cfg.get("llm_provider")
                or settings.llm_provider
                or DEFAULT_LLM_PROVIDER
            )
            .strip()
            .lower()
        )
        sub_cfg = providers_map.get(target_provider, {})
        env_matches = target_provider == (
            settings.llm_provider or DEFAULT_LLM_PROVIDER
        ).strip().lower()
        test_key = sub_cfg.get("api_key") or (
            _secret_value(settings.llm_api_key) if env_matches else None
        )
        test_model = sub_cfg.get("llm_model") or (
            settings.llm_model if env_matches else None
        )
        return _test_llm(target_provider, test_key, test_model)
    return _test_groq(cfg.get("api_key") or _secret_value(settings.groq_api_key))


def _test_discord(webhook_url: str | None) -> IntegrationTestResponse:
    if not webhook_url:
        return IntegrationTestResponse(
            ok=False, detail="Webhook do Discord não configurado."
        )
    parsed = urlparse(webhook_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return IntegrationTestResponse(
            ok=False, detail="URL do webhook do Discord inválida."
        )
    try:
        response = httpx.post(
            webhook_url,
            json={
                "content": (
                    "✅ Teste de conexão do **CortechX Zumo** "
                    "realizado com sucesso."
                )
            },
            timeout=10.0,
        )
        if 200 <= response.status_code < 300:
            return IntegrationTestResponse(
                ok=True, detail="Mensagem de teste enviada para o Discord."
            )
        return IntegrationTestResponse(
            ok=False,
            detail=f"Discord retornou status HTTP {response.status_code}.",
        )
    except httpx.HTTPError as exc:
        return IntegrationTestResponse(
            ok=False, detail=f"Falha ao contatar o Discord: {exc.__class__.__name__}."
        )


def _test_notion(
    api_key: str | None, database_id: str | None
) -> IntegrationTestResponse:
    if not api_key or not database_id:
        return IntegrationTestResponse(
            ok=False, detail="Token ou Database ID do Notion não configurado."
        )
    try:
        normalized_db_id = str(UUID(database_id.strip()))
    except (ValueError, AttributeError):
        normalized_db_id = database_id.strip()

    try:
        client = NotionClient(auth=api_key.strip())
        try:
            client.data_sources.retrieve(data_source_id=normalized_db_id)
        except AttributeError:
            client.databases.retrieve(database_id=normalized_db_id)
        except APIResponseError as ds_exc:
            if ds_exc.status != 404:
                raise
            client.databases.retrieve(database_id=normalized_db_id)
        return IntegrationTestResponse(
            ok=True, detail="Conexão com a database do Notion validada com sucesso."
        )
    except APIResponseError as exc:
        return IntegrationTestResponse(
            ok=False, detail=f"Erro na API do Notion (status {exc.status})."
        )
    except Exception as exc:
        return IntegrationTestResponse(
            ok=False, detail=f"Falha ao conectar ao Notion: {exc.__class__.__name__}."
        )


def _test_obsidian(
    vault_path: str | None, notes_folder: str | None
) -> IntegrationTestResponse:
    if not vault_path:
        return IntegrationTestResponse(
            ok=False, detail="Caminho do vault do Obsidian não configurado."
        )
    try:
        vault = Path(vault_path).expanduser().resolve(strict=True)
    except OSError:
        return IntegrationTestResponse(
            ok=False, detail="O diretório do vault não existe ou não é acessível."
        )
    if not vault.is_dir():
        return IntegrationTestResponse(
            ok=False, detail="O caminho do vault não é um diretório válido."
        )

    folder = (notes_folder or DEFAULT_OBSIDIAN_NOTES_FOLDER).strip()
    parts = folder.replace("\\", "/").split("/")
    if (
        folder.startswith(("/", "\\"))
        or any(part in {".", ".."} for part in parts)
        or ":" in parts[0]
    ):
        return IntegrationTestResponse(
            ok=False, detail="Pasta de notas do Obsidian inválida."
        )

    notes_dir = (vault / folder).resolve()
    if not notes_dir.is_relative_to(vault):
        return IntegrationTestResponse(
            ok=False, detail="Pasta de notas fora do diretório do vault."
        )

    try:
        notes_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=".zumo-test-", suffix=".tmp", dir=notes_dir
        )
        os.close(fd)
        Path(temp_name).unlink(missing_ok=True)
        return IntegrationTestResponse(
            ok=True, detail=f"Vault gravável verificado em {notes_dir}."
        )
    except OSError as exc:
        err = exc.strerror or exc
        return IntegrationTestResponse(
            ok=False,
            detail=f"Sem permissão de escrita no vault: {err}.",
        )


def _test_groq(api_key: str | None) -> IntegrationTestResponse:
    if not api_key or not api_key.strip():
        return IntegrationTestResponse(
            ok=False, detail="Chave da API Groq não configurada."
        )
    clean_key = api_key.strip()
    if not clean_key.startswith("gsk_") or len(clean_key) < 16:
        return IntegrationTestResponse(
            ok=False,
            detail="Formato de chave Groq inválido (esperado prefixo 'gsk_').",
        )
    try:
        response = httpx.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {clean_key}"},
            timeout=10.0,
        )
        if response.status_code == 200:
            return IntegrationTestResponse(
                ok=True, detail="Chave da API Groq validada com sucesso."
            )
        if response.status_code in {401, 403}:
            return IntegrationTestResponse(
                ok=False, detail="Chave Groq rejeitada pela API (não autorizada)."
            )
        return IntegrationTestResponse(
            ok=False,
            detail=f"Groq retornou status HTTP {response.status_code}.",
        )
    except httpx.HTTPError as exc:
        return IntegrationTestResponse(
            ok=False, detail=f"Falha ao contatar a Groq: {exc.__class__.__name__}."
        )


def _test_llm(
    provider_name: str, api_key: str | None, model: str | None
) -> IntegrationTestResponse:
    normalized = provider_name.strip().lower()
    if normalized not in SUPPORTED_LLM_PROVIDERS:
        return IntegrationTestResponse(
            ok=False, detail=f"Provedor LLM não suportado: {provider_name}."
        )
    if not api_key or not api_key.strip():
        return IntegrationTestResponse(
            ok=False, detail="Chave de API de LLM não configurada."
        )
    clean_key = api_key.strip()
    raw_model = (
        model or DEFAULT_LLM_MODELS.get(normalized, DEFAULT_LLM_MODEL)
    ).strip()
    clean_model = (
        raw_model[len("models/") :]
        if normalized == "gemini" and raw_model.startswith("models/")
        else raw_model
    )
    if (
        not clean_model
        or ".." in clean_model.split("/")
        or not _LLM_MODEL_RE.fullmatch(clean_model)
    ):
        return IntegrationTestResponse(
            ok=False, detail=f"Nome de modelo inválido para {normalized}."
        )

    provider_labels = {
        "gemini": "Gemini",
        "openai": "OpenAI",
        "groq": "Groq",
        "anthropic": "Anthropic",
    }
    label = provider_labels[normalized]

    try:
        if normalized == "gemini":
            response = httpx.get(
                f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}",
                headers={"x-goog-api-key": clean_key},
                timeout=10.0,
            )
        elif normalized == "openai":
            response = httpx.get(
                f"https://api.openai.com/v1/models/{clean_model}",
                headers={"Authorization": f"Bearer {clean_key}"},
                timeout=10.0,
            )
        elif normalized == "groq":
            response = httpx.get(
                f"https://api.groq.com/openai/v1/models/{clean_model}",
                headers={"Authorization": f"Bearer {clean_key}"},
                timeout=10.0,
            )
        else:
            response = httpx.get(
                f"https://api.anthropic.com/v1/models/{clean_model}",
                headers={
                    "x-api-key": clean_key,
                    "anthropic-version": "2023-06-01",
                },
                timeout=10.0,
            )

        if response.status_code == 200:
            return IntegrationTestResponse(
                ok=True, detail=f"Chave {label} validada com sucesso."
            )
        if response.status_code in {400, 401, 403}:
            return IntegrationTestResponse(
                ok=False,
                detail=(
                    f"Chave {label} inválida ou sem permissão para acessar este modelo."
                ),
            )
        if response.status_code == 404:
            return IntegrationTestResponse(
                ok=False,
                detail=f"Modelo '{clean_model}' não encontrado na API do {label}.",
            )
        return IntegrationTestResponse(
            ok=False,
            detail=f"API do {label} retornou status HTTP {response.status_code}.",
        )
    except httpx.HTTPError as exc:
        return IntegrationTestResponse(
            ok=False,
            detail=f"Falha ao contatar a API do {label}: {exc.__class__.__name__}.",
        )
