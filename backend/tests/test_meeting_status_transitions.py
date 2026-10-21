from app.models.meeting_status import VALID_TRANSITIONS, MeetingStatus


def test_main_pipeline_transitions_are_valid():
    flow = [
        MeetingStatus.RECEIVED,
        MeetingStatus.AUDIO_UPLOADED,
        MeetingStatus.TRANSCRIBING,
        MeetingStatus.TRANSCRIBED,
        MeetingStatus.PROCESSING,
        MeetingStatus.COMPLETED,
    ]
    for current, target in zip(flow, flow[1:]):
        assert target in VALID_TRANSITIONS[current]


def test_processing_can_fail_and_be_retried():
    assert MeetingStatus.FAILED in VALID_TRANSITIONS[MeetingStatus.PROCESSING]
    assert MeetingStatus.PROCESSING in VALID_TRANSITIONS[MeetingStatus.FAILED]


def test_completed_meeting_can_be_reprocessed():
    assert MeetingStatus.PROCESSING in VALID_TRANSITIONS[MeetingStatus.COMPLETED]


def test_processing_can_rollback_to_audio_uploaded():
    assert MeetingStatus.AUDIO_UPLOADED in VALID_TRANSITIONS[MeetingStatus.PROCESSING]
