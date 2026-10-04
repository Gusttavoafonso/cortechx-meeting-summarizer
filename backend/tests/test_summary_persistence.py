from datetime import date

import pytest
from app.models.meeting import Meeting
from app.models.summary import Summary
from app.models.task import Task
from app.repositories.summary_repository import (
    SummaryMeetingNotFoundError,
    SummaryRepository,
)
from app.schemas.summary import SummaryResult, TaskItem
from pydantic import ValidationError


def _create_meeting(db_session, title: str = "Reuniao de planejamento") -> Meeting:
    meeting = Meeting(title=title)
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)
    return meeting


def _result() -> SummaryResult:
    return SummaryResult(
        objective="Alinhar a entrega do backend.",
        summary="A equipe revisou o andamento e definiu prazos.",
        key_points=["Backend em andamento", "Front depende da API"],
        decisions=["Finalizar o backend ate sexta-feira"],
        tasks=[
            TaskItem(
                description="Finalizar endpoints de resumo",
                responsible="Ana",
                deadline=date(2026, 10, 2),
            ),
            TaskItem(description="Revisar migrations"),
        ],
    )


def test_summary_defaults_for_json_lists_and_timestamps(db_session):
    meeting = _create_meeting(db_session)
    summary = Summary(meeting_id=meeting.id)

    db_session.add(summary)
    db_session.commit()
    db_session.refresh(summary)

    assert summary.key_points == []
    assert summary.decisions == []
    assert summary.structured_result is None
    assert summary.generation_metadata is None
    assert summary.created_at is not None
    assert summary.updated_at is not None


def test_save_result_persists_summary_and_tasks(db_session):
    meeting = _create_meeting(db_session)
    repository = SummaryRepository(db_session)

    summary = repository.save_result(
        meeting.id,
        _result(),
        generation_metadata={"provider": "gemini", "chunks": 3},
    )

    assert summary.id is not None
    assert summary.meeting_id == meeting.id
    assert summary.objective == "Alinhar a entrega do backend."
    assert summary.summary == "A equipe revisou o andamento e definiu prazos."
    assert summary.key_points == ["Backend em andamento", "Front depende da API"]
    assert summary.decisions == ["Finalizar o backend ate sexta-feira"]
    assert summary.generation_metadata == {"provider": "gemini", "chunks": 3}
    assert summary.structured_result["tasks"][0]["deadline"] == "2026-10-02"

    tasks = repository.list_tasks(meeting.id)
    assert [t.description for t in tasks] == [
        "Finalizar endpoints de resumo",
        "Revisar migrations",
    ]
    assert [t.position for t in tasks] == [0, 1]
    assert tasks[0].responsible == "Ana"
    assert tasks[0].deadline == date(2026, 10, 2)
    assert tasks[1].responsible is None
    assert tasks[1].deadline is None


def test_save_result_reprocessing_replaces_summary_and_tasks(db_session):
    meeting = _create_meeting(db_session)
    repository = SummaryRepository(db_session)

    first = repository.save_result(meeting.id, _result())
    first_id = first.id

    new_result = SummaryResult(
        summary="Resumo reprocessado.",
        decisions=[],
        tasks=[TaskItem(description="Unica tarefa nova")],
    )
    second = repository.save_result(meeting.id, new_result)

    assert second.id == first_id
    assert second.summary == "Resumo reprocessado."
    assert second.objective is None
    assert second.key_points == []
    assert second.decisions == []

    tasks = repository.list_tasks(meeting.id)
    assert [t.description for t in tasks] == ["Unica tarefa nova"]
    assert db_session.query(Summary).count() == 1
    assert db_session.query(Task).count() == 1


def test_save_result_unknown_meeting_raises(db_session):
    repository = SummaryRepository(db_session)

    with pytest.raises(SummaryMeetingNotFoundError):
        repository.save_result(9999, _result())


def test_deleting_meeting_removes_summary_and_tasks(db_session):
    meeting = _create_meeting(db_session)
    repository = SummaryRepository(db_session)
    repository.save_result(meeting.id, _result())

    db_session.delete(meeting)
    db_session.commit()

    assert db_session.query(Summary).count() == 0
    assert db_session.query(Task).count() == 0


def test_summary_result_normalizes_and_validates():
    result = SummaryResult(
        objective="   ",
        summary="Resumo",
        key_points=["  ponto  ", "", "   "],
        tasks=[TaskItem(description="  fazer algo  ", responsible="  ")],
    )

    assert result.objective is None
    assert result.key_points == ["ponto"]
    assert result.tasks[0].description == "fazer algo"
    assert result.tasks[0].responsible is None

    with pytest.raises(ValidationError):
        TaskItem(description="   ")

    with pytest.raises(ValidationError):
        SummaryResult(summary="")


def test_summary_response_includes_tasks(db_session):
    from app.schemas.summary import SummaryResponse

    meeting = _create_meeting(db_session)
    repository = SummaryRepository(db_session)
    summary = repository.save_result(meeting.id, _result())

    response = SummaryResponse.model_validate(summary)
    assert len(response.tasks) == 2
    assert response.tasks[0].description == "Finalizar endpoints de resumo"
    assert response.tasks[0].responsible == "Ana"
    assert response.tasks[0].deadline == date(2026, 10, 2)
    assert response.tasks[1].description == "Revisar migrations"
    assert response.tasks[1].responsible is None


def test_get_summary_endpoint_returns_tasks(client, db_session):
    meeting = _create_meeting(db_session)
    repository = SummaryRepository(db_session)
    repository.save_result(meeting.id, _result())

    resp = client.get(f"/meetings/{meeting.id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["meeting_id"] == meeting.id
    assert data["objective"] == "Alinhar a entrega do backend."
    assert len(data["tasks"]) == 2
    assert data["tasks"][0]["description"] == "Finalizar endpoints de resumo"
    assert data["tasks"][0]["responsible"] == "Ana"
    assert data["tasks"][0]["deadline"] == "2026-10-02"


def test_get_summary_endpoint_not_found(client):
    resp = client.get("/meetings/99999/summary")
    assert resp.status_code == 404
    assert "não encontrada" in resp.json()["detail"]


def test_get_summary_endpoint_unprocessed(client, db_session):
    meeting = _create_meeting(db_session)
    resp = client.get(f"/meetings/{meeting.id}/summary")
    assert resp.status_code == 404
    assert "Resumo ainda não gerado" in resp.json()["detail"]

