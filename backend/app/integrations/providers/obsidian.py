from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from app.core.config import settings
from app.integrations.base import IntegrationProvider
from app.integrations.providers.formatters.obsidian import ObsidianFormatter
from app.integrations.registry import register_provider
from app.schemas.integration import IntegrationResult, MeetingIntegrationPayload

logger = logging.getLogger(__name__)
_INVALID_FILENAME = re.compile(r'[\\/:*?"<>|#^\[\]\x00-\x1f\x7f]')
_MAX_FILENAME_BYTES = 180


@register_provider("obsidian")
class ObsidianProvider(IntegrationProvider):
    """Grava notas Markdown em um vault do Obsidian acessível localmente."""

    name = "obsidian"

    def __init__(
        self,
        vault_path: str | Path | SecretStr | None = None,
        notes_folder: str | None = None,
        *,
        formatter: ObsidianFormatter | None = None,
        **kwargs: Any,
    ) -> None:
        raw_vault = (
            vault_path
            if vault_path is not None
            else kwargs.get("obsidian_vault_path")
        )
        if raw_vault is None:
            raw_vault = settings.obsidian_vault_path
        if isinstance(raw_vault, SecretStr):
            raw_vault = raw_vault.get_secret_value()
        self.vault_path = Path(raw_vault).expanduser() if raw_vault else None

        raw_folder = (
            notes_folder
            if notes_folder is not None
            else kwargs.get("obsidian_notes_folder")
        )
        self.notes_folder = str(
            raw_folder if raw_folder is not None else settings.obsidian_notes_folder
        ).strip()
        self.formatter = formatter or ObsidianFormatter()

    def send(self, payload: MeetingIntegrationPayload) -> IntegrationResult:
        if self.vault_path is None:
            return self._failure(
                payload.meeting_id,
                "Caminho do vault do Obsidian não configurado.",
            )

        temporary_path: Path | None = None
        try:
            vault = self.vault_path.resolve(strict=True)
            if not vault.is_dir():
                return self._failure(payload.meeting_id, "Vault do Obsidian inválido.")

            relative_folder = self._validated_folder()
            notes_dir = (vault / relative_folder).resolve()
            if not notes_dir.is_relative_to(vault):
                return self._failure(
                    payload.meeting_id,
                    "Pasta de notas do Obsidian inválida.",
                )
            notes_dir.mkdir(parents=True, exist_ok=True)
            notes_dir = notes_dir.resolve(strict=True)
            if not notes_dir.is_relative_to(vault) or not notes_dir.is_dir():
                return self._failure(
                    payload.meeting_id,
                    "Pasta de notas do Obsidian inválida.",
                )

            filename = self._existing_filename(notes_dir, payload.meeting_id)
            if filename is None:
                filename = self._filename(payload)
            destination = notes_dir / filename
            if not destination.resolve().parent.is_relative_to(notes_dir):
                return self._failure(
                    payload.meeting_id,
                    "Destino da nota do Obsidian inválido.",
                )

            content = self.formatter.format(payload)
            file_descriptor, temporary_name = tempfile.mkstemp(
                prefix=".obsidian-", suffix=".tmp", dir=notes_dir
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as note:
                note.write(content)
                note.flush()
                os.fsync(note.fileno())
            os.replace(temporary_path, destination)
            temporary_path = None

            return IntegrationResult(
                provider=self.name,
                success=True,
                metadata={
                    "meeting_id": payload.meeting_id,
                    "filename": filename,
                    "external_id": filename,
                },
            )
        except Exception as exc:
            logger.warning(
                "Falha ao gravar nota da reunião %s no Obsidian (%s).",
                payload.meeting_id,
                type(exc).__name__,
            )
            return self._failure(payload.meeting_id, self._safe_error(exc))
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Não foi possível remover temporário do Obsidian.")

    def _validated_folder(self) -> Path:
        normalized = self.notes_folder.replace("\\", "/")
        folder = Path(normalized)
        if (
            not normalized
            or folder.is_absolute()
            or any(part in {".", ".."} for part in normalized.split("/"))
            or (folder.parts and ":" in folder.parts[0])
        ):
            raise ValueError("Invalid notes folder")
        return folder

    @classmethod
    def _filename(cls, payload: MeetingIntegrationPayload) -> str:
        title = _INVALID_FILENAME.sub("", payload.title)
        title = " ".join(title.split()).rstrip(". ") or "Reunião"
        suffix = f" ({payload.meeting_id}).md"
        meeting_date = (
            payload.created_at.date().isoformat()
            if payload.created_at
            else "sem-data"
        )
        prefix = f"{meeting_date} - "
        budget = _MAX_FILENAME_BYTES - len((prefix + suffix).encode("utf-8"))
        encoded = title.encode("utf-8")[: max(budget, 0)]
        while encoded:
            try:
                title = encoded.decode("utf-8").rstrip(". ")
                break
            except UnicodeDecodeError:
                encoded = encoded[:-1]
        title = title or "Reunião"
        return f"{prefix}{title}{suffix}"

    @staticmethod
    def _existing_filename(notes_dir: Path, meeting_id: int) -> str | None:
        matches = list(notes_dir.glob(f"* ({meeting_id}).md"))
        if len(matches) > 1:
            raise ValueError("Multiple notes for meeting")
        if not matches:
            return None
        match = matches[0]
        if match.is_symlink() or not match.is_file():
            raise ValueError("Invalid existing note")
        return match.name

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        if isinstance(exc, (FileNotFoundError, NotADirectoryError)):
            return "Vault do Obsidian não encontrado."
        if isinstance(exc, PermissionError):
            return "Sem permissão para gravar no vault do Obsidian."
        if isinstance(exc, ValueError):
            return "Configuração ou destino do Obsidian inválido."
        return "Não foi possível gravar a nota no Obsidian."

    def _failure(self, meeting_id: int, message: str) -> IntegrationResult:
        return IntegrationResult(
            provider=self.name,
            success=False,
            error=message,
            metadata={"meeting_id": meeting_id},
        )
