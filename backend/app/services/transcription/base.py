from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings


@dataclass
class SegmentData:
    text: str
    start: float | None = None
    end: float | None = None
    speaker: str | None = None


@dataclass
class TranscriptionResult:
    text: str
    segments: list[SegmentData] = field(default_factory=list)
    language: str | None = None
    duration: float | None = None


class BaseSpeechToTextService(ABC):
    """Interface base para provedores de Speech-to-Text."""

    @abstractmethod
    def transcribe(
        self,
        audio_path: str | Path,
        language: str = "pt",
    ) -> TranscriptionResult:
        """Transcreve o arquivo de áudio especificado."""
        pass


def get_speech_to_text_service() -> BaseSpeechToTextService:
    """Factory para instanciar o serviço de STT adequado.

    Se GROQ_API_KEY estiver configurada, utiliza GroqWhisperService (nuvem).
    Caso contrário, utiliza FasterWhisperService (local) com modelo configurado.
    """
    if settings.groq_api_key and settings.groq_api_key.get_secret_value().strip():
        from app.services.transcription.groq_whisper_service import (
            GroqWhisperService,
        )

        return GroqWhisperService(
            api_key=settings.groq_api_key.get_secret_value().strip()
        )

    from app.services.transcription.faster_whisper_service import (
        FasterWhisperService,
    )

    return FasterWhisperService(
        model_size=settings.WHISPER_MODEL_SIZE,
        device=settings.WHISPER_DEVICE,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
    )
