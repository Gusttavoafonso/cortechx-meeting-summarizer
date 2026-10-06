from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.exceptions import is_recoverable

logger = logging.getLogger(__name__)

# Padrões para detecção e higienização de informações sensíveis
_REDACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # 1. Chaves de API conhecidas
    (re.compile(r"gsk_[a-zA-Z0-9]{16,}", re.IGNORECASE), "gsk_***[REDACTED]"),
    (re.compile(r"AIza[a-zA-Z0-9_\-]{35}", re.IGNORECASE), "AIza***[REDACTED]"),
    (re.compile(r"hf_[a-zA-Z0-9]{20,}", re.IGNORECASE), "hf_***[REDACTED]"),
    (re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE), "sk-***[REDACTED]"),
    # 2. Tokens de autenticação / Bearer / Basic
    (re.compile(r"(?i)\b(bearer\s+)[a-zA-Z0-9_\-\.]{15,}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b(basic\s+)[a-zA-Z0-9+/=]{15,}"), r"\1[REDACTED]"),
    # 3. Pares chave/valor sensíveis (api_key=..., token: ..., password=...)
    (
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|secret|password|passwd|auth|authorization|credencial|credential)\s*[:=]\s*['\"]?([^\s,;'\"&]{4,})['\"]?"
        ),
        r"\1=[REDACTED]",
    ),
    # 4. Query params de URL contendo tokens/chaves
    (
        re.compile(r"(?i)([?&](api_key|token|auth|key|secret)=)[^&\s]+"),
        r"\1[REDACTED]",
    ),
]


def sanitize_error_message(message: str) -> str:
    """Remove tokens, chaves de API e credenciais de mensagens de erro."""
    if not message:
        return ""
    sanitized = str(message)
    for pattern, replacement in _REDACT_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized.strip()


@dataclass(frozen=True)
class FailureRecord:
    """Registro estruturado de falha de processamento de reunião (Issue #26 - Etapa 9)."""

    stage: str
    error_type: str
    message: str
    attempts: int
    timestamp: str
    is_recoverable: bool

    def to_dict(self) -> dict[str, Any]:
        """Converte o registro para dicionário serializável."""
        return asdict(self)


class FailureRecorder:
    """Gerenciador de registro seguro de informações sobre falhas."""

    @staticmethod
    def record_failure(
        stage: str,
        error: BaseException,
        attempts: int = 1,
    ) -> FailureRecord:
        """Registra contexto mínimo da falha sem expor informações sensíveis."""
        cleaned_msg = sanitize_error_message(str(error))
        if not cleaned_msg:
            cleaned_msg = error.__class__.__name__

        record = FailureRecord(
            stage=stage or "unknown",
            error_type=error.__class__.__name__,
            message=cleaned_msg,
            attempts=max(1, attempts),
            timestamp=datetime.now(timezone.utc).isoformat(),
            is_recoverable=is_recoverable(error),
        )

        logger.error(
            "Falha registrada no pipeline [etapa=%s | tipo=%s | tentativas=%d | recuperavel=%s | horario=%s]: %s",
            record.stage,
            record.error_type,
            record.attempts,
            record.is_recoverable,
            record.timestamp,
            record.message,
            extra={"failure_record": record.to_dict()},
        )

        return record
