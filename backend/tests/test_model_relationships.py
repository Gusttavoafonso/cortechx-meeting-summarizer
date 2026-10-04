from app.models.meeting import Meeting
from app.models.summary import Summary
from app.models.task import Task
from app.models.transcript import Transcript
from app.models.transcript_segment import TranscriptSegment


def test_meeting_relationships(db_session):
    meeting = Meeting(title="Reuniao com relacionamentos")

    transcript = Transcript(
        raw_text="Transcricao completa da reuniao.",
    )

    segment = TranscriptSegment(
        speaker="Pessoa 1",
        start_time=0.0,
        end_time=10.0,
        text="Primeiro trecho da reuniao.",
    )

    summary = Summary(
        objective="Planejar a sprint.",
        summary="Definir as principais tarefas.",
        key_points=["Escopo da sprint"],
        decisions=["Backend fecha na sexta"],
        structured_result={
            "tasks": ["Implementar funcionalidade"]
        },
    )

    task = Task(position=0, description="Implementar funcionalidade")
    meeting.tasks.append(task)

    transcript.segments.append(segment)
    meeting.transcript = transcript
    meeting.summary = summary

    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    assert meeting.transcript is not None
    assert meeting.transcript.raw_text == "Transcricao completa da reuniao."

    assert len(meeting.transcript.segments) == 1
    assert meeting.transcript.segments[0].speaker == "Pessoa 1"

    assert meeting.summary is not None
    assert meeting.summary.objective == "Planejar a sprint."
    assert meeting.summary.summary == "Definir as principais tarefas."
    assert meeting.summary.key_points == ["Escopo da sprint"]
    assert meeting.summary.decisions == ["Backend fecha na sexta"]
    assert meeting.summary.updated_at is not None

    assert len(meeting.tasks) == 1
    assert meeting.tasks[0].meeting_id == meeting.id


def test_meeting_cascade_delete(db_session):
    meeting = Meeting(title="Reuniao para exclusao")

    transcript = Transcript(
        raw_text="Transcricao que deve ser removida.",
    )

    segment = TranscriptSegment(
        speaker="Pessoa 1",
        text="Segmento que deve ser removido.",
    )

    summary = Summary(
        objective="Resumo que deve ser removido.",
    )

    task = Task(position=0, description="Tarefa que deve ser removida.")
    meeting.tasks.append(task)

    transcript.segments.append(segment)
    meeting.transcript = transcript
    meeting.summary = summary

    db_session.add(meeting)
    db_session.commit()

    transcript_id = transcript.id
    segment_id = segment.id
    summary_id = summary.id
    task_id = task.id

    db_session.delete(meeting)
    db_session.commit()

    assert db_session.get(Transcript, transcript_id) is None
    assert db_session.get(TranscriptSegment, segment_id) is None
    assert db_session.get(Summary, summary_id) is None
    assert db_session.get(Task, task_id) is None
