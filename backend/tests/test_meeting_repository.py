from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.repositories.meeting_repository import MeetingRepository


def test_create_meeting(db_session):
    repository = MeetingRepository(db_session)

    meeting = Meeting(title="Reuniao de teste")

    created = repository.create(meeting)

    assert created.id is not None
    assert created.title == "Reuniao de teste"
    assert created.status == MeetingStatus.RECEIVED


def test_get_meeting_by_id(db_session):
    repository = MeetingRepository(db_session)

    meeting = repository.create(
        Meeting(title="Reuniao para busca")
    )

    found = repository.get_by_id(meeting.id)

    assert found is not None
    assert found.id == meeting.id
    assert found.title == "Reuniao para busca"


def test_list_all_meetings(db_session):
    repository = MeetingRepository(db_session)

    repository.create(
        Meeting(title="Reuniao 1")
    )

    repository.create(
        Meeting(title="Reuniao 2")
    )

    meetings = repository.list_all()

    assert len(meetings) == 2