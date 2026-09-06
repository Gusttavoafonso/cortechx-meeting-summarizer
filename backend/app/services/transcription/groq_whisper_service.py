from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.services.transcription.base import (
    BaseSpeechToTextService,
    SegmentData,
    TranscriptionResult,
)

logger = logging.getLogger(__name__)


class GroqWhisperService(BaseSpeechToTextService):
    """Implementação de Speech-to-Text na nuvem via Groq API (whisper-large-v3)."""

    def __init__(
        self,
        api_key: str,
        model: str = "whisper-large-v3",
    ) -> None:
        if not api_key or not str(api_key).strip():
            raise ValueError(
                "Chave de API da Groq ausente ou inválida. "
                "Configure GROQ_API_KEY no arquivo .env."
            )
        self.api_key = api_key.strip()
        self.model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from groq import Groq

            self._client = Groq(api_key=self.api_key)
        return self._client

    def transcribe(
        self,
        audio_path: str | Path,
        language: str = "pt",
    ) -> TranscriptionResult:
        """Transcreve o arquivo de áudio utilizando a API da Groq."""
        path_obj = Path(audio_path)
        if not path_obj.is_file():
            raise FileNotFoundError(
                f"Arquivo de áudio não encontrado para transcrição: {path_obj}"
            )

        client = self._get_client()

        logger.info(
            f"Enviando áudio '{path_obj.name}' para a Groq com modelo {self.model}..."
        )

        with open(path_obj, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                file=(path_obj.name, audio_file.read()),
                model=self.model,
                response_format="verbose_json",
                language=language,
            )

        # Trata resposta que pode ser objeto Pydantic ou dicionário
        text = (
            getattr(response, "text", None)
            or (response.get("text") if isinstance(response, dict) else "")
            or ""
        )
        raw_segments = (
            getattr(response, "segments", None)
            or (response.get("segments") if isinstance(response, dict) else None)
            or []
        )
        duration = getattr(response, "duration", None) or (
            response.get("duration") if isinstance(response, dict) else None
        )
        detected_language = (
            getattr(response, "language", None)
            or (response.get("language") if isinstance(response, dict) else None)
            or language
        )

        segments: list[SegmentData] = []
        for seg in raw_segments:
            seg_start = getattr(seg, "start", None) or (
                seg.get("start") if isinstance(seg, dict) else None
            )
            seg_end = getattr(seg, "end", None) or (
                seg.get("end") if isinstance(seg, dict) else None
            )
            seg_text = getattr(seg, "text", None) or (
                seg.get("text") if isinstance(seg, dict) else ""
            )

            if seg_text and seg_text.strip():
                start_val = (
                    round(float(seg_start), 2) if seg_start is not None else None
                )
                end_val = round(float(seg_end), 2) if seg_end is not None else None
                segments.append(
                    SegmentData(
                        start=start_val,
                        end=end_val,
                        text=seg_text.strip(),
                    )
                )

        logger.info(
            f"Transcrição Groq concluída com sucesso: {len(segments)} segmentos."
        )

        return TranscriptionResult(
            text=text.strip(),
            segments=segments,
            language=detected_language,
            duration=round(float(duration), 2) if duration is not None else None,
        )
