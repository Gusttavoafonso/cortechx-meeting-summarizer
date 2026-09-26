from unittest.mock import MagicMock, call

import pytest
from app.models.meeting_status import MeetingStatus
from app.services.processing.meeting_processor import MeetingProcessor


@pytest.fixture
def processor_dependencies() -> dict[str, MagicMock]:
    return {
        "meeting_repository": MagicMock(),
        "transcript_repository": MagicMock(),
        "audio_storage_service": MagicMock(),
        "speech_to_text_service": MagicMock(),
        "diarization_service": MagicMock(),
        "chunking_service": MagicMock(),
    }


@pytest.fixture
def processor(
    processor_dependencies: dict[str, MagicMock],
) -> MeetingProcessor:
    return MeetingProcessor(**processor_dependencies)


@pytest.fixture
def meeting() -> MagicMock:
    meeting = MagicMock()
    meeting.id = 1
    meeting.status = MeetingStatus.AUDIO_UPLOADED
    meeting.audio = MagicMock()
    meeting.audio.file_path = "uploads/meeting.wav"
    return meeting


def test_process_meeting_completes_pipeline(
    processor: MeetingProcessor,
    processor_dependencies: dict[str, MagicMock],
    meeting: MagicMock,
) -> None:
    meeting_repository = processor_dependencies["meeting_repository"]
    transcript_repository = processor_dependencies["transcript_repository"]
    audio_storage_service = processor_dependencies["audio_storage_service"]
    speech_to_text_service = processor_dependencies["speech_to_text_service"]
    diarization_service = processor_dependencies["diarization_service"]
    chunking_service = processor_dependencies["chunking_service"]

    stt_result = MagicMock(text="Texto transcrito", segments=[MagicMock()])
    transcript = MagicMock()
    diarization_segments = [MagicMock()]
    audio_path = "/tmp/meeting.wav"

    meeting_repository.get_by_id.return_value = meeting
    audio_storage_service.get_file_path.return_value = audio_path
    speech_to_text_service.transcribe.return_value = stt_result
    transcript_repository.save_transcript.return_value = transcript
    diarization_service.diarize.return_value = diarization_segments

    processor.process_meeting(meeting.id)

    speech_to_text_service.transcribe.assert_called_once_with(audio_path)
    transcript_repository.save_transcript.assert_called_once_with(
        meeting_id=meeting.id,
        content=stt_result.text,
        segments=stt_result.segments,
    )
    diarization_service.diarize.assert_called_once_with(audio_path)
    transcript_repository.apply_diarization.assert_called_once_with(
        transcript,
        diarization_segments,
    )
    chunking_service.split.assert_called_once_with(transcript)
    assert meeting_repository.update_status.call_args_list == [
        call(meeting, MeetingStatus.PROCESSING),
        call(meeting, MeetingStatus.COMPLETED),
    ]


def test_process_meeting_raises_when_meeting_does_not_exist(
    processor: MeetingProcessor,
    processor_dependencies: dict[str, MagicMock],
) -> None:
    meeting_repository = processor_dependencies["meeting_repository"]
    meeting_repository.get_by_id.return_value = None

    with pytest.raises(ValueError, match="not found"):
        processor.process_meeting(1)

    meeting_repository.update_status.assert_not_called()


def test_process_meeting_raises_when_audio_is_missing() -> None:
    meeting_repository = MagicMock()
    transcript_repository = MagicMock()
    audio_storage_service = MagicMock()
    speech_to_text_service = MagicMock()
    diarization_service = MagicMock()
    processor = MeetingProcessor(
        meeting_repository=meeting_repository,
        transcript_repository=transcript_repository,
        audio_storage_service=audio_storage_service,
        speech_to_text_service=speech_to_text_service,
        diarization_service=diarization_service,
        chunking_service=MagicMock(),
    )
    meeting = MagicMock()
    meeting.audio = None
    meeting_repository.get_by_id.return_value = meeting

    with pytest.raises(ValueError, match="Missing audio"):
        processor.process_meeting(1)

    meeting_repository.update_status.assert_not_called()


def test_process_meeting_raises_when_already_processing(
    processor: MeetingProcessor,
    processor_dependencies: dict[str, MagicMock],
    meeting: MagicMock,
) -> None:
    meeting_repository = processor_dependencies["meeting_repository"]
    meeting.status = MeetingStatus.PROCESSING
    meeting_repository.get_by_id.return_value = meeting

    with pytest.raises(ValueError, match="already being processed"):
        processor.process_meeting(meeting.id)

    meeting_repository.update_status.assert_not_called()
    processor_dependencies["speech_to_text_service"].transcribe.assert_not_called()


def test_process_meeting_marks_as_failed_when_stt_fails(
    processor: MeetingProcessor,
    processor_dependencies: dict[str, MagicMock],
    meeting: MagicMock,
) -> None:
    meeting_repository = processor_dependencies["meeting_repository"]
    speech_to_text_service = processor_dependencies["speech_to_text_service"]
    audio_storage_service = processor_dependencies["audio_storage_service"]
    meeting_repository.get_by_id.return_value = meeting
    audio_storage_service.get_file_path.return_value = "/tmp/meeting.wav"
    speech_to_text_service.transcribe.side_effect = RuntimeError("STT failed")

    with pytest.raises(RuntimeError, match="STT failed"):
        processor.process_meeting(meeting.id)

    assert meeting_repository.update_status.call_args_list == [
        call(meeting, MeetingStatus.PROCESSING),
        call(meeting, MeetingStatus.FAILED),
    ]
    processor_dependencies["diarization_service"].diarize.assert_not_called()


def test_process_meeting_marks_as_failed_when_transcript_persistence_fails(
    processor: MeetingProcessor,
    processor_dependencies: dict[str, MagicMock],
    meeting: MagicMock,
) -> None:
    meeting_repository = processor_dependencies["meeting_repository"]
    transcript_repository = processor_dependencies["transcript_repository"]
    speech_to_text_service = processor_dependencies["speech_to_text_service"]
    audio_storage_service = processor_dependencies["audio_storage_service"]
    meeting_repository.get_by_id.return_value = meeting
    audio_storage_service.get_file_path.return_value = "/tmp/meeting.wav"
    speech_to_text_service.transcribe.return_value = MagicMock(
        text="Texto transcrito",
        segments=[MagicMock()],
    )
    transcript_repository.save_transcript.side_effect = RuntimeError("Database failed")

    with pytest.raises(RuntimeError, match="Database failed"):
        processor.process_meeting(meeting.id)

    assert meeting_repository.update_status.call_args_list == [
        call(meeting, MeetingStatus.PROCESSING),
        call(meeting, MeetingStatus.FAILED),
    ]
    processor_dependencies["diarization_service"].diarize.assert_not_called()


def test_process_meeting_marks_as_failed_when_diarization_fails(
    processor: MeetingProcessor,
    processor_dependencies: dict[str, MagicMock],
    meeting: MagicMock,
) -> None:
    meeting_repository = processor_dependencies["meeting_repository"]
    transcript_repository = processor_dependencies["transcript_repository"]
    speech_to_text_service = processor_dependencies["speech_to_text_service"]
    audio_storage_service = processor_dependencies["audio_storage_service"]
    diarization_service = processor_dependencies["diarization_service"]
    meeting_repository.get_by_id.return_value = meeting
    audio_storage_service.get_file_path.return_value = "/tmp/meeting.wav"
    speech_to_text_service.transcribe.return_value = MagicMock(
        text="Texto transcrito",
        segments=[MagicMock()],
    )
    transcript_repository.save_transcript.return_value = MagicMock()
    diarization_service.diarize.side_effect = RuntimeError("Diarization failed")

    with pytest.raises(RuntimeError, match="Diarization failed"):
        processor.process_meeting(meeting.id)

    assert meeting_repository.update_status.call_args_list == [
        call(meeting, MeetingStatus.PROCESSING),
        call(meeting, MeetingStatus.FAILED),
    ]
    transcript_repository.apply_diarization.assert_not_called()


def test_process_meeting_marks_as_failed_when_diarization_persistence_fails(
    processor: MeetingProcessor,
    processor_dependencies: dict[str, MagicMock],
    meeting: MagicMock,
) -> None:
    meeting_repository = processor_dependencies["meeting_repository"]
    transcript_repository = processor_dependencies["transcript_repository"]
    speech_to_text_service = processor_dependencies["speech_to_text_service"]
    audio_storage_service = processor_dependencies["audio_storage_service"]
    diarization_service = processor_dependencies["diarization_service"]
    meeting_repository.get_by_id.return_value = meeting
    audio_storage_service.get_file_path.return_value = "/tmp/meeting.wav"
    speech_to_text_service.transcribe.return_value = MagicMock(
        text="Texto transcrito",
        segments=[MagicMock()],
    )
    transcript = MagicMock()
    transcript_repository.save_transcript.return_value = transcript
    diarization_service.diarize.return_value = [MagicMock()]
    transcript_repository.apply_diarization.side_effect = RuntimeError(
        "Diarization persistence failed"
    )

    with pytest.raises(RuntimeError, match="Diarization persistence failed"):
        processor.process_meeting(meeting.id)

    assert meeting_repository.update_status.call_args_list == [
        call(meeting, MeetingStatus.PROCESSING),
        call(meeting, MeetingStatus.FAILED),
    ]


def test_process_meeting_marks_as_failed_when_chunking_fails(
    processor: MeetingProcessor,
    processor_dependencies: dict[str, MagicMock],
    meeting: MagicMock,
) -> None:
    meeting_repository = processor_dependencies["meeting_repository"]
    transcript_repository = processor_dependencies["transcript_repository"]
    speech_to_text_service = processor_dependencies["speech_to_text_service"]
    audio_storage_service = processor_dependencies["audio_storage_service"]
    diarization_service = processor_dependencies["diarization_service"]
    chunking_service = processor_dependencies["chunking_service"]
    meeting_repository.get_by_id.return_value = meeting
    audio_storage_service.get_file_path.return_value = "/tmp/meeting.wav"
    speech_to_text_service.transcribe.return_value = MagicMock(
        text="Texto transcrito",
        segments=[MagicMock()],
    )
    transcript = MagicMock()
    transcript_repository.save_transcript.return_value = transcript
    diarization_service.diarize.return_value = [MagicMock()]
    chunking_service.split.side_effect = RuntimeError("Chunking failed")

    with pytest.raises(RuntimeError, match="Chunking failed"):
        processor.process_meeting(meeting.id)

    assert meeting_repository.update_status.call_args_list == [
        call(meeting, MeetingStatus.PROCESSING),
        call(meeting, MeetingStatus.FAILED),
    ]
