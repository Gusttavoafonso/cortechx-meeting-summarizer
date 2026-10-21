from enum import Enum


class MeetingStatus(str, Enum):
    """Estados persistidos do ciclo de vida de uma reunião.

    RECEIVED: reunião criada, ainda sem áudio.
    AUDIO_UPLOADED: áudio persistido e disponível para processamento.
    TRANSCRIBING: transcrição em execução.
    TRANSCRIBED: transcrição persistida; pronta para análise/sumarização.
    PROCESSING: sumarização/análise em execução.
    COMPLETED: pipeline solicitado concluído e resultado persistido.
    FAILED: última execução falhou definitivamente; pode ser tentada novamente.
    """

    RECEIVED = "received"
    AUDIO_UPLOADED = "audio_uploaded"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            for member in cls:
                if member.value == value.lower():
                    return member
        return None


# Transições permitidas. Falhas podem ser retomadas a partir do estado apropriado.
VALID_TRANSITIONS: dict[MeetingStatus, set[MeetingStatus]] = {
    MeetingStatus.RECEIVED: {
        MeetingStatus.AUDIO_UPLOADED,
        MeetingStatus.FAILED,
    },
    MeetingStatus.AUDIO_UPLOADED: {
        MeetingStatus.TRANSCRIBING,
        MeetingStatus.PROCESSING,
        MeetingStatus.FAILED,
    },
    MeetingStatus.TRANSCRIBING: {
        MeetingStatus.AUDIO_UPLOADED,
        MeetingStatus.TRANSCRIBED,
        MeetingStatus.FAILED,
    },
    MeetingStatus.TRANSCRIBED: {
        MeetingStatus.PROCESSING,
        MeetingStatus.TRANSCRIBING,
        MeetingStatus.AUDIO_UPLOADED,
        MeetingStatus.FAILED,
    },
    MeetingStatus.PROCESSING: {
        MeetingStatus.COMPLETED,
        MeetingStatus.FAILED,
        MeetingStatus.TRANSCRIBED,
        MeetingStatus.AUDIO_UPLOADED,
    },
    MeetingStatus.COMPLETED: {
        MeetingStatus.PROCESSING,
        MeetingStatus.AUDIO_UPLOADED,
    },
    MeetingStatus.FAILED: {
        MeetingStatus.AUDIO_UPLOADED,
        MeetingStatus.TRANSCRIBING,
        MeetingStatus.PROCESSING,
    },
}

IN_PROGRESS_STATUSES: frozenset[MeetingStatus] = frozenset(
    {MeetingStatus.TRANSCRIBING, MeetingStatus.PROCESSING}
)