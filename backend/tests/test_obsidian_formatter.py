import json
from datetime import date, datetime

import pytest
from app.integrations.providers.formatters import ObsidianFormatter
from app.schemas.integration import MeetingIntegrationPayload, TaskIntegrationPayload


def _payload(**overrides) -> MeetingIntegrationPayload:
    values = {
        "meeting_id": 12,
        "title": "Reunião de planejamento",
        "summary": "A equipe definiu as prioridades.",
        "objective": "Organizar a sprint.",
        "key_points": ["Backend", "Testes"],
        "decisions": ["Publicar na sexta-feira"],
        "tasks": [
            TaskIntegrationPayload(
                description="Revisar API",
                responsible="Ana",
                deadline=date(2026, 10, 30),
            )
        ],
        "created_at": datetime(2026, 10, 20, 14, 30),
    }
    values.update(overrides)
    return MeetingIntegrationPayload(**values)


def test_formats_all_fields():
    note = ObsidianFormatter().format(_payload())

    assert note == (
        "---\n"
        "meeting_id: 12\n"
        'title: "Reunião de planejamento"\n'
        "date: 2026-10-20\n"
        "tags: [reuniao]\n"
        "---\n"
        "\n"
        "# Reunião de planejamento\n"
        "\n"
        "## Objetivo\n"
        "Organizar a sprint.\n"
        "\n"
        "## Resumo\n"
        "A equipe definiu as prioridades.\n"
        "\n"
        "## Pontos principais\n"
        "- Backend\n"
        "- Testes\n"
        "\n"
        "## Decisões\n"
        "- Publicar na sexta-feira\n"
        "\n"
        "## Tarefas\n"
        "- [ ] Revisar API — Ana 📅 2026-10-30\n"
    )


def test_omits_empty_sections():
    note = ObsidianFormatter().format(
        _payload(objective=None, key_points=[], decisions=[], tasks=[])
    )

    for section in ("Objetivo", "Pontos principais", "Decisões", "Tarefas"):
        assert f"## {section}" not in note
    assert "## Resumo" in note


def test_omits_date_when_created_at_is_missing():
    note = ObsidianFormatter().format(_payload(created_at=None))

    assert "date:" not in note


def test_discards_blank_items_and_omits_section():
    note = ObsidianFormatter().format(
        _payload(key_points=["  ", ""], decisions=["Decisão", "   "])
    )

    assert "## Pontos principais" not in note
    assert note.count("- Decisão") == 1


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        (
            TaskIntegrationPayload(description="Revisar", deadline=date(2026, 10, 30)),
            "- [ ] Revisar 📅 2026-10-30",
        ),
        (
            TaskIntegrationPayload(description="Revisar", responsible="Ana"),
            "- [ ] Revisar — Ana",
        ),
        (TaskIntegrationPayload(description="Revisar"), "- [ ] Revisar"),
        (
            TaskIntegrationPayload(description="Revisar", deadline="2026-10-30"),
            "- [ ] Revisar 📅 2026-10-30",
        ),
        (
            TaskIntegrationPayload(description="Revisar", deadline="próxima semana"),
            "- [ ] Revisar (prazo: próxima semana)",
        ),
        (
            TaskIntegrationPayload(description="Revisar\n\nAPI", responsible="  "),
            "- [ ] Revisar API",
        ),
    ],
)
def test_formats_task_variants(task, expected):
    note = ObsidianFormatter().format(_payload(tasks=[task]))

    assert note.endswith(f"## Tarefas\n{expected}\n")


def test_ignores_task_with_blank_description():
    task = TaskIntegrationPayload(description="   ")

    note = ObsidianFormatter().format(_payload(tasks=[task]))

    assert "## Tarefas" not in note


@pytest.mark.parametrize(
    "title",
    [
        'Plano: "Fase 2"',
        "Revisão: ação & decisão #1 [teste]",
        "Aspas 'simples' e \\ barra",
        "Título\ncom quebra\n---\n# falso cabeçalho",
    ],
)
def test_frontmatter_title_is_valid_and_round_trips(title):
    note = ObsidianFormatter().format(_payload(title=title))

    front = note.split("---\n")[1]
    title_line = next(line for line in front.splitlines() if line.startswith("title:"))
    # JSON entre aspas duplas é YAML válido; o round-trip prova o escape correto.
    assert json.loads(title_line.removeprefix("title: ")) == " ".join(title.split())
    assert len(front.splitlines()) == 4


def test_multiline_title_does_not_create_extra_heading():
    note = ObsidianFormatter().format(_payload(title="Linha 1\n## Injetado"))

    assert "\n## Injetado" not in note
    assert "# Linha 1 ## Injetado\n" in note


def test_ends_with_single_newline():
    note = ObsidianFormatter().format(_payload())

    assert note.endswith("\n") and not note.endswith("\n\n")
