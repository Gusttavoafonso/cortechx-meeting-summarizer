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

# Cache de instâncias do WhisperModel para evitar recarga de modelos
# pesados em RAM a cada requisição
_MODEL_CACHE: dict[tuple[str, str, str], Any] = {}


class FasterWhisperService(BaseSpeechToTextService):
    """Implementação de Speech-to-Text local utilizando faster-whisper e Silero VAD."""

    def __init__(
        self,
        model_size: str = "small",
        device: str = "auto",
        compute_type: str = "auto",
        vad_filter: bool = True,
        min_silence_duration_ms: int = 500,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.vad_filter = vad_filter
        self.min_silence_duration_ms = min_silence_duration_ms

    def _get_model(self) -> Any:
        cache_key = (self.model_size, self.device, self.compute_type)
        if cache_key not in _MODEL_CACHE:
            logger.info(
                f"Carregando modelo faster-whisper '{self.model_size}' "
                f"(device={self.device}, compute_type={self.compute_type})..."
            )
            from faster_whisper import WhisperModel

            _MODEL_CACHE[cache_key] = WhisperModel(
                model_size_or_path=self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("Modelo faster-whisper carregado e armazenado em cache.")
        return _MODEL_CACHE[cache_key]

    def transcribe(
        self,
        audio_path: str | Path,
        language: str = "pt",
    ) -> TranscriptionResult:
        """Transcreve o arquivo local utilizando faster-whisper com Silero VAD."""
        path_str = str(audio_path)
        if not Path(path_str).is_file():
            raise FileNotFoundError(
                f"Arquivo de áudio não encontrado para transcrição: {path_str}"
            )

        model = self._get_model()
        vad_parameters = {
            "min_silence_duration_ms": self.min_silence_duration_ms,
        }

        logger.info(
            f"Iniciando transcrição de '{path_str}' com VAD={self.vad_filter}..."
        )
        segments_gen, info = model.transcribe(
            path_str,
            language=language,
            vad_filter=self.vad_filter,
            vad_parameters=vad_parameters if self.vad_filter else None,
        )

        segments: list[SegmentData] = []
        text_parts: list[str] = []

        for seg in segments_gen:
            text = seg.text.strip()
            if text:
                text_parts.append(text)
                segments.append(
                    SegmentData(
                        start=round(seg.start, 2),
                        end=round(seg.end, 2),
                        text=text,
                    )
                )

        full_text = " ".join(text_parts)
        duration = (
            round(info.duration, 2) if info and info.duration is not None else None
        )
        detected_language = info.language if info else language

        logger.info(
            f"Transcrição concluída: {len(segments)} segmentos extraídos, "
            f"idioma={detected_language}, duração={duration}s."
        )

        return TranscriptionResult(
            text=full_text,
            segments=segments,
            language=detected_language,
            duration=duration,
        )
