from datetime import date

from app.integrations.providers.formatters.discord import DiscordFormatter
from app.schemas.integration import MeetingIntegrationPayload, TaskIntegrationPayload


def _payload(**overrides) -> MeetingIntegrationPayload:
    values = {
        "meeting_id": 1,
        "title": "Planejamento da Sprint",
        "summary": "A equipe definiu as prioridades da próxima entrega.",
        "objective": "Organizar o trabalho da sprint.",
        "key_points": ["Backend", "Testes"],
        "decisions": ["Publicar na sexta-feira"],
        "tasks": [
            TaskIntegrationPayload(
                description="Revisar API",
                responsible="Ana",
                deadline=date(2026, 10, 16),
            )
        ],
    }
    values.update(overrides)
    return MeetingIntegrationPayload(**values)


def test_formats_all_meeting_sections():
    message = DiscordFormatter().format(_payload())

    assert message == [
        "## Reunião: Planejamento da Sprint\n\n### Resumo\n"
        "A equipe definiu as prioridades da próxima entrega.\n\n### Objetivo\n"
        "Organizar o trabalho da sprint.\n\n### Principais pontos\n- Backend\n"
        "- Testes\n\n### Decisões\n- Publicar na sexta-feira\n\n### Tarefas\n"
        "- [ ] Revisar API (Responsável: Ana | Prazo: 2026-10-16)"
    ]


def test_omits_optional_empty_sections_and_task_details():
    messages = DiscordFormatter().format(
        _payload(
            objective="  ",
            key_points=[],
            decisions=[],
            tasks=[
                TaskIntegrationPayload(description="Documentar fluxo"),
                TaskIntegrationPayload(description="Criar endpoint", deadline="  "),
            ],
        )
    )

    assert messages == [
        "## Reunião: Planejamento da Sprint\n\n### Resumo\n"
        "A equipe definiu as prioridades da próxima entrega.\n\n### Tarefas\n"
        "- [ ] Documentar fluxo\n- [ ] Criar endpoint"
    ]
    assert "None" not in messages[0]
    assert "Prazo:" not in messages[0]


def test_splits_long_content_without_losing_text():
    summary = "x" * 4_001
    messages = DiscordFormatter().format(
        _payload(
            summary=summary,
            objective=None,
            key_points=[],
            decisions=[],
            tasks=[],
        )
    )

    assert all(len(message) <= 2_000 for message in messages)
    assert "".join(messages).count("x") == len(summary)
