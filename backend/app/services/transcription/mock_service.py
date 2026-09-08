from __future__ import annotations

from pathlib import Path

from app.services.transcription.base import (
    BaseSpeechToTextService,
    SegmentData,
    TranscriptionResult,
)


class MockSpeechToTextService(BaseSpeechToTextService):
    """Serviço mock de Speech-to-Text para testes automatizados rápidos e isolados."""

    def __init__(
        self,
        canned_result: TranscriptionResult | None = None,
    ) -> None:
        self.canned_result = canned_result
        self.call_count = 0
        self.last_audio_path: str | Path | None = None
        self.last_language: str | None = None

    def transcribe(
        self,
        audio_path: str | Path,
        language: str = "pt",
    ) -> TranscriptionResult:
        self.call_count += 1
        self.last_audio_path = audio_path
        self.last_language = language

        if self.canned_result is not None:
            return self.canned_result

        # Resultado padrão realista
        return TranscriptionResult(
            text=(
                "Bom dia a todos. Vamos iniciar o alinhamento semanal do projeto "
                "Cortechx. Primeiro ponto é o pipeline de transcrição."
            ),
            segments=[
                SegmentData(
                    start=0.0,
                    end=3.5,
                    text=(
                        "Bom dia a todos. Vamos iniciar o "
                        "alinhamento semanal do projeto Cortechx."
                    ),
                    speaker=None,
                ),
                SegmentData(
                    start=3.6,
                    end=6.8,
                    text="Primeiro ponto é o pipeline de transcrição.",
                    speaker=None,
                ),
            ],
            language=language,
            duration=6.8,
        )
