from datetime import date, datetime, timezone

from app.integrations.providers.formatters.notion import NotionFormatter
from app.schemas.integration import (
    MeetingIntegrationPayload,
    TaskIntegrationPayload,
)


def payload(**overrides):
    base = dict(
        meeting_id=123,
        title="Reunião de teste",
        summary="Resumo da reunião.",
        objective="Validar a integração.",
        key_points=["Ponto importante"],
        decisions=["Decisão aprovada"],
        tasks=[
            TaskIntegrationPayload(
                id=1,
                description="Criar documentação",
                responsible="Equipe",
                deadline=date(2026, 10, 20),
            )
        ],
        created_at=datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return MeetingIntegrationPayload(**base)


def texts(blocks):
    return [
        "".join(
            item["text"]["content"]
            for item in block[block["type"]]["rich_text"]
        )
        for block in blocks
    ]


def types(blocks):
    return [block["type"] for block in blocks]


def test_properties_contain_title_meeting_id_and_status():
    properties = NotionFormatter().properties(payload())

    assert properties["Name"]["title"][0]["text"]["content"] == "Reunião de teste"
    assert properties["meeting_id"]["number"] == 123
    assert properties["Status"]["select"]["name"] == "Pendente"
    assert properties["Data"]["date"]["start"] == "2026-10-13"


def test_properties_omit_date_when_missing():
    properties = NotionFormatter().properties(payload(created_at=None))

    assert "Data" not in properties


def test_blocks_contain_all_sections():
    blocks = NotionFormatter().blocks(payload())
    content = texts(blocks)

    assert "Objetivo" in content
    assert "Resumo" in content
    assert "Principais pontos" in content
    assert "Decisões" in content
    assert "Tarefas" in content
    assert "Resumo da reunião." in content


def test_optional_sections_are_omitted():
    blocks = NotionFormatter().blocks(
        payload(objective=None, key_points=[], decisions=[], tasks=[])
    )
    content = texts(blocks)

    assert content == ["Resumo", "Resumo da reunião."]


def test_blocks_without_tasks_have_no_task_section():
    blocks = NotionFormatter().blocks(payload(tasks=[]))

    assert "Tarefas" not in texts(blocks)


def test_task_without_responsible_is_grouped_as_unassigned():
    blocks = NotionFormatter().blocks(
        payload(
            tasks=[
                TaskIntegrationPayload(description="Tarefa solta"),
            ]
        )
    )
    content = texts(blocks)

    assert "Sem responsável" in content
    assert "Tarefa solta" in content


def test_tasks_are_grouped_by_responsible():
    blocks = NotionFormatter().blocks(
        payload(
            tasks=[
                TaskIntegrationPayload(
                    description="Revisar backend", responsible="Gustavo"
                ),
                TaskIntegrationPayload(
                    description="Atualizar documentação", responsible="João"
                ),
                TaskIntegrationPayload(
                    description="Subir o deploy", responsible="Gustavo"
                ),
            ]
        )
    )
    content = texts(blocks)

    kinds = types(blocks)

    # Um subtítulo por responsável, mesmo com mais de uma tarefa.
    assert content.count("Gustavo") == 1
    assert content.count("João") == 1

    gustavo = content.index("Gustavo")
    joao = content.index("João")

    assert kinds[gustavo] == "heading_3"
    assert kinds[gustavo + 1] == "bulleted_list_item"
    assert content[gustavo + 1] == "Revisar backend"
    assert content[gustavo + 2] == "Subir o deploy"
    assert content[joao + 1] == "Atualizar documentação"


def test_task_deadline_is_preserved():
    blocks = NotionFormatter().blocks(
        payload(
            tasks=[
                TaskIntegrationPayload(
                    description="Revisar backend",
                    responsible="Gustavo",
                    deadline=date(2026, 10, 20),
                )
            ]
        )
    )

    assert "Revisar backend — Prazo: 2026-10-20" in texts(blocks)


def test_task_deadline_accepts_text():
    blocks = NotionFormatter().blocks(
        payload(
            tasks=[
                TaskIntegrationPayload(
                    description="Revisar backend",
                    deadline="sexta-feira",
                )
            ]
        )
    )

    assert "Revisar backend — Prazo: sexta-feira" in texts(blocks)


def test_long_summary_is_split_without_loss():
    summary = "a" * 5_000
    blocks = NotionFormatter().blocks(payload(summary=summary))
    paragraphs = [
        block for block in blocks if block["type"] == "paragraph"
    ]

    rebuilt = "".join(
        item["text"]["content"]
        for block in paragraphs
        for item in block["paragraph"]["rich_text"]
    )

    assert summary in rebuilt
    assert all(
        len(item["text"]["content"]) <= NotionFormatter.text_limit
        for block in paragraphs
        for item in block["paragraph"]["rich_text"]
    )


def test_long_title_is_not_truncated():
    title = "t" * 4_500
    properties = NotionFormatter().properties(payload(title=title))
    items = properties["Name"]["title"]

    assert "".join(item["text"]["content"] for item in items) == title
    assert all(
        len(item["text"]["content"]) <= NotionFormatter.text_limit
        for item in items
    )
