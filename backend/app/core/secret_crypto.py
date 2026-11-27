from __future__ import annotations

import base64
import binascii
import logging
import os
import threading
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings

logger = logging.getLogger(__name__)

ENCRYPTED_PREFIX = "enc:v1:"
SENSITIVE_CONFIG_FIELDS = frozenset({"api_key", "webhook_url"})

_ENCRYPTION_SALT = b"cortechx-user-secrets-v1"
_EXPLICIT_KEY_INFO = b"encryption-key-user-secrets-aes256"
_JWT_FALLBACK_INFO = b"jwt-fallback-user-secrets-aes256"

_fallback_warn_lock = threading.Lock()
_warned_jwt_fallback = False


class SecretDecryptionError(ValueError):
    """Falha ao decodificar ou autenticar um segredo criptografado."""


def _derive_aes_key(master_material: str, *, info: bytes) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_ENCRYPTION_SALT,
        info=info,
    )
    return hkdf.derive(master_material.encode("utf-8"))


def _get_key_ring() -> list[bytes]:
    global _warned_jwt_fallback

    raw_encryption_key = (
        settings.encryption_key.get_secret_value()
        if settings.encryption_key is not None
        else ""
    )
    entries = [part.strip() for part in raw_encryption_key.split(",") if part.strip()]
    if entries:
        return [_derive_aes_key(entry, info=_EXPLICIT_KEY_INFO) for entry in entries]

    with _fallback_warn_lock:
        if not _warned_jwt_fallback:
            logger.warning(
                "ENCRYPTION_KEY não definida; derivando chave AES-256-GCM para "
                "segredos de usuários a partir de JWT_SECRET_KEY."
            )
            _warned_jwt_fallback = True

    jwt_secret = settings.JWT_SECRET_KEY.get_secret_value()
    return [_derive_aes_key(jwt_secret, info=_JWT_FALLBACK_INFO)]


def _build_aad(*, user_id: int, provider: str, field: str) -> bytes:
    return (
        f"user:{user_id}:provider:{provider.strip().lower()}:field:{field.strip()}"
    ).encode("utf-8")


def is_encrypted(value: str | None) -> bool:
    return isinstance(value, str) and value.startswith(ENCRYPTED_PREFIX)


def encrypt_secret(
    plaintext: str,
    *,
    user_id: int,
    provider: str,
    field: str,
) -> str:
    key = _get_key_ring()[0]
    nonce = os.urandom(12)
    aad = _build_aad(user_id=user_id, provider=provider, field=field)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), aad)
    encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"{ENCRYPTED_PREFIX}{encoded}"


def decrypt_secret(
    value: str,
    *,
    user_id: int,
    provider: str,
    field: str,
) -> str:
    if not isinstance(value, str):
        raise SecretDecryptionError("Formato inválido para segredo armazenado.")

    if not is_encrypted(value):
        return value.strip()

    token = value[len(ENCRYPTED_PREFIX) :]
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
    except (ValueError, binascii.Error) as exc:
        raise SecretDecryptionError("Payload criptografado inválido.") from exc

    if len(raw) < 12 + 16:
        raise SecretDecryptionError("Payload criptografado incompleto.")

    nonce, ciphertext = raw[:12], raw[12:]
    aad = _build_aad(user_id=user_id, provider=provider, field=field)

    for key in _get_key_ring():
        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
            return plaintext.decode("utf-8")
        except (InvalidTag, UnicodeDecodeError):
            continue

    raise SecretDecryptionError(
        "Não foi possível autenticar ou descriptografar o segredo do usuário."
    )


def encrypt_config_secrets(
    config: dict[str, Any],
    *,
    user_id: int,
    provider: str,
) -> dict[str, Any]:
    result = dict(config)
    for field in SENSITIVE_CONFIG_FIELDS:
        val = result.get(field)
        if isinstance(val, str) and val.strip() and not is_encrypted(val):
            result[field] = encrypt_secret(
                val.strip(),
                user_id=user_id,
                provider=provider,
                field=field,
            )

    raw_providers = result.get("providers")
    if isinstance(raw_providers, dict):
        encrypted_providers: dict[str, Any] = {}
        for sub_provider, sub_cfg in raw_providers.items():
            if not isinstance(sub_cfg, dict):
                encrypted_providers[sub_provider] = sub_cfg
                continue
            updated_sub = dict(sub_cfg)
            for field in SENSITIVE_CONFIG_FIELDS:
                val = updated_sub.get(field)
                if isinstance(val, str) and val.strip() and not is_encrypted(val):
                    updated_sub[field] = encrypt_secret(
                        val.strip(),
                        user_id=user_id,
                        provider=provider,
                        field=f"providers.{sub_provider.strip().lower()}.{field}",
                    )
            encrypted_providers[sub_provider] = updated_sub
        result["providers"] = encrypted_providers

    return result


def decrypt_config_secrets(
    config: dict[str, Any],
    *,
    user_id: int,
    provider: str,
) -> dict[str, Any]:
    result = dict(config)
    for field in SENSITIVE_CONFIG_FIELDS:
        val = result.get(field)
        if isinstance(val, str) and val.strip():
            result[field] = decrypt_secret(
                val,
                user_id=user_id,
                provider=provider,
                field=field,
            )

    raw_providers = result.get("providers")
    if isinstance(raw_providers, dict):
        decrypted_providers: dict[str, Any] = {}
        for sub_provider, sub_cfg in raw_providers.items():
            if not isinstance(sub_cfg, dict):
                decrypted_providers[sub_provider] = sub_cfg
                continue
            updated_sub = dict(sub_cfg)
            for field in SENSITIVE_CONFIG_FIELDS:
                val = updated_sub.get(field)
                if isinstance(val, str) and val.strip():
                    updated_sub[field] = decrypt_secret(
                        val,
                        user_id=user_id,
                        provider=provider,
                        field=f"providers.{sub_provider.strip().lower()}.{field}",
                    )
            decrypted_providers[sub_provider] = updated_sub
        result["providers"] = decrypted_providers

    return result
