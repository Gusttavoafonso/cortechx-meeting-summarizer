from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.integrations.delivery import enabled_providers_from_settings
from app.integrations.providers import obsidian as obsidian_module
from app.integrations.providers.obsidian import ObsidianProvider
from app.integrations.registry import default_registry
from app.integrations.service import IntegrationService
from app.schemas.integration import MeetingIntegrationPayload, TaskIntegrationPayload


def _payload(**overrides) -> MeetingIntegrationPayload:
    values = {
        "meeting_id": 41,
        "title": "Planejamento da sprint",
        "summary": "A equipe alinhou as prioridades.",
        "objective": "Organizar as entregas.",
        "key_points": ["Revisar a API"],
        "decisions": ["Publicar na sexta-feira"],
        "tasks": [
            TaskIntegrationPayload(
                description="Implementar endpoint",
                responsible="Ana",
                deadline="2026-10-30",
            )
        ],
        "created_at": datetime(2026, 10, 20, 14, 30),
    }
    values.update(overrides)
    return MeetingIntegrationPayload(**values)


def test_writes_note_with_optional_meeting_sections_missing(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    payload = _payload(objective=None, key_points=[], decisions=[], tasks=[])

    result = ObsidianProvider(vault_path=vault).send(payload)

    assert result.success is True
    filename = result.metadata["filename"]
    note = (vault / "Reuniões" / filename).read_text(encoding="utf-8")
    assert "## Resumo\nA equipe alinhou as prioridades." in note
    assert "## Objetivo" not in note
    assert "## Pontos principais" not in note
    assert "## Decisões" not in note
    assert "## Tarefas" not in note


def test_writes_task_when_responsible_and_deadline_are_missing(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    payload = _payload(
        tasks=[TaskIntegrationPayload(description="Revisar o documento")]
    )

    result = ObsidianProvider(vault_path=vault).send(payload)

    note = (vault / "Reuniões" / result.metadata["filename"]).read_text(
        encoding="utf-8"
    )
    assert "- [ ] Revisar o documento\n" in note
    assert "None" not in note


def test_sanitizes_title_and_limits_filename_length(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    payload = _payload(title="../Plano: #1 [ação]" + "á" * 300)

    result = ObsidianProvider(vault_path=vault).send(payload)

    filename = result.metadata["filename"]
    assert result.success is True
    assert len(filename.encode("utf-8")) <= 180
    assert not any(char in filename for char in "\\/:*?\"<>|#^[]")
    assert (vault / "Reuniões" / filename).is_file()
    assert list(vault.rglob("*.md")) == [vault / "Reuniões" / filename]


def test_missing_date_uses_stable_sem_data_prefix(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()

    result = ObsidianProvider(vault_path=vault).send(_payload(created_at=None))

    assert result.success is True
    assert result.metadata["filename"].startswith("sem-data - ")


def test_resending_meeting_overwrites_same_note_even_if_title_changes(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    provider = ObsidianProvider(vault_path=vault)

    first = provider.send(_payload())
    original_name = first.metadata["filename"]
    second = provider.send(_payload(title="Título atualizado", created_at=None))

    notes = list((vault / "Reuniões").glob("*.md"))
    assert first.success is second.success is True
    assert second.metadata["filename"] == original_name
    assert notes == [vault / "Reuniões" / original_name]
    assert "# Título atualizado" in notes[0].read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("vault_path", "notes_folder", "expected_error"),
    [
        (None, "Reuniões", "não configurado"),
        ("<vault-inexistente>", "Reuniões", "não encontrado"),
        ("<vault>", "../fora", "inválido"),
    ],
)
def test_invalid_configuration_returns_safe_failure(
    tmp_path: Path,
    vault_path: str | None,
    notes_folder: str,
    expected_error: str,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    if vault_path == "<vault>":
        vault_path = str(vault)
    elif vault_path == "<vault-inexistente>":
        vault_path = str(vault / "missing")

    result = ObsidianProvider(
        vault_path=vault_path,
        notes_folder=notes_folder,
    ).send(_payload())

    assert result.success is False
    assert expected_error in result.error.lower()
    assert str(vault) not in result.error
    assert str(vault) not in str(result.metadata)


def test_write_permission_error_returns_safe_failure_without_vault_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    real_mkdir = Path.mkdir

    def deny_notes_directory(self: Path, *args, **kwargs) -> None:
        if self == vault / "Reuniões":
            raise PermissionError("denied: " + str(vault))
        real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", deny_notes_directory)

    result = ObsidianProvider(vault_path=vault).send(_payload())

    assert result.success is False
    assert "permissão" in result.error.lower()
    assert str(vault) not in result.error
    assert str(vault) not in str(result.metadata)


def test_atomic_replace_failure_preserves_previous_note_and_cleans_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    provider = ObsidianProvider(vault_path=vault)
    first = provider.send(_payload())
    destination = vault / "Reuniões" / first.metadata["filename"]
    previous_content = destination.read_text(encoding="utf-8")
    replace = Mock(side_effect=OSError("I/O failed: " + str(vault)))
    monkeypatch.setattr(obsidian_module.os, "replace", replace)

    result = provider.send(_payload(summary="Novo resumo"))

    assert result.success is False
    assert str(vault) not in result.error
    assert str(vault) not in str(result.metadata)
    assert destination.read_text(encoding="utf-8") == previous_content
    assert list((vault / "Reuniões").glob(".obsidian-*.tmp")) == []


def test_provider_is_registered_and_runs_through_integration_service(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()

    assert default_registry.get("obsidian") is ObsidianProvider
    result = IntegrationService().send(
        "obsidian",
        _payload(),
        vault_path=vault,
        notes_folder="Atas/2026",
    )

    assert result.success is True
    assert (vault / "Atas" / "2026" / result.metadata["filename"]).is_file()


def test_obsidian_setting_includes_provider_in_automatic_delivery_list() -> None:
    enabled = enabled_providers_from_settings(
        SimpleNamespace(
            discord_enabled=False,
            notion_enabled=False,
            obsidian_enabled=True,
        )
    )

    assert enabled == ["obsidian"]
