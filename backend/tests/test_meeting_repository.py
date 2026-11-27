from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.repositories.meeting_repository import MeetingRepository


def test_create_meeting(db_session):
    repository = MeetingRepository(db_session)

    status_type = Meeting.__table__.c.status.type
    assert status_type.enums == [status.value for status in MeetingStatus]

    meeting = Meeting(title="Reuniao de teste")

    created = repository.create(meeting)

    assert created.id is not None
    assert created.title == "Reuniao de teste"
    assert created.status == MeetingStatus.RECEIVED


def test_get_meeting_by_id(db_session, create_user):
    repository = MeetingRepository(db_session)
    owner = create_user()

    meeting = repository.create(Meeting(title="Reuniao para busca", user_id=owner.id))

    found = repository.get_by_id(meeting.id, owner.id)

    assert found is not None
    assert found.id == meeting.id
    assert found.title == "Reuniao para busca"


def test_list_all_meetings(db_session, create_user):
    repository = MeetingRepository(db_session)
    owner = create_user()

    repository.create(Meeting(title="Reuniao 1", user_id=owner.id))

    repository.create(Meeting(title="Reuniao 2", user_id=owner.id))

    meetings = repository.list_all(owner.id)

    assert len(meetings) == 2
