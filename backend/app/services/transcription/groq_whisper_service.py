from __future__ import annotations

import io
import logging
import wave
from pathlib import Path
from typing import Any

import numpy as np

from app.services.transcription.base import (
    BaseSpeechToTextService,
    SegmentData,
    TranscriptionResult,
)

logger = logging.getLogger(__name__)

# Limite de segurança de tamanho de arquivo aceito pela API da Groq (25 MB)
GROQ_MAX_FILE_SIZE_BYTES = 24 * 1024 * 1024  # 24 MB (margem de 1 MB)


def _extract_field(obj: Any, key: str, default: Any = None) -> Any:
    """Extrai campo de objeto ou dict preservando valores falsy (ex: 0.0)."""
    if hasattr(obj, key):
        val = getattr(obj, key)
        return val if val is not None else default
    if isinstance(obj, dict):
        val = obj.get(key)
        return val if val is not None else default
    return default


def _audio_chunk_to_wav_bytes(
    chunk_samples: np.ndarray, sample_rate: int = 16000
) -> bytes:
    """Converte array numpy float32 em bytes de áudio WAV 16kHz mono (16-bit PCM)."""
    int16_samples = np.clip(chunk_samples * 32767.0, -32768.0, 32767.0).astype(np.int16)
    bio = io.BytesIO()
    with wave.open(bio, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(int16_samples.tobytes())
    return bio.getvalue()


class GroqWhisperService(BaseSpeechToTextService):
    """Implementação de Speech-to-Text na nuvem via Groq API (whisper-large-v3).

    Suporta arquivos de qualquer tamanho:
    - Arquivos <= 24 MB são transmitidos diretamente.
    - Arquivos > 24 MB são particionados de forma transparente em janelas de ~10 min
      guiadas por pausas de silêncio identificadas via Silero VAD.
    """

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

    def _parse_groq_response(
        self,
        response: Any,
        offset_seconds: float = 0.0,
        default_language: str = "pt",
    ) -> tuple[str, list[SegmentData], str, float | None]:
        text = _extract_field(response, "text", "") or ""
        raw_segments = _extract_field(response, "segments", []) or []
        duration = _extract_field(response, "duration", None)
        detected_language = _extract_field(response, "language", default_language)

        segments: list[SegmentData] = []
        for seg in raw_segments:
            seg_start = _extract_field(seg, "start", None)
            seg_end = _extract_field(seg, "end", None)
            seg_text = _extract_field(seg, "text", "") or ""

            if seg_text and seg_text.strip():
                start_val = (
                    round(float(seg_start) + offset_seconds, 2)
                    if seg_start is not None
                    else None
                )
                end_val = (
                    round(float(seg_end) + offset_seconds, 2)
                    if seg_end is not None
                    else None
                )
                segments.append(
                    SegmentData(
                        start=start_val,
                        end=end_val,
                        text=seg_text.strip(),
                    )
                )

        parsed_duration = round(float(duration), 2) if duration is not None else None
        return (
            text.strip(),
            segments,
            str(detected_language),
            parsed_duration,
        )

    def _calculate_cut_points(
        self,
        total_samples: int,
        sample_rate: int = 16000,
        speech_timestamps: list[dict[str, int]] | None = None,
        target_seconds: int = 600,
    ) -> list[int]:
        """Calcula os pontos de corte ideais aproveitando pausas de silêncio."""
        target_samples = target_seconds * sample_rate
        if total_samples <= target_samples:
            return [total_samples]

        cuts: list[int] = []
        current_start = 0

        while current_start + target_samples < total_samples:
            ideal_cut = current_start + target_samples
            best_cut = ideal_cut
            min_distance = float("inf")

            if speech_timestamps:
                search_min = ideal_cut - (60 * sample_rate)
                search_max = ideal_cut + (60 * sample_rate)

                for i in range(len(speech_timestamps) - 1):
                    gap_start = speech_timestamps[i]["end"]
                    gap_end = speech_timestamps[i + 1]["start"]
                    if (
                        gap_start >= search_min
                        and gap_end <= search_max
                        and gap_end > gap_start
                    ):
                        midpoint = (gap_start + gap_end) // 2
                        dist = abs(midpoint - ideal_cut)
                        if dist < min_distance:
                            min_distance = dist
                            best_cut = midpoint

            cuts.append(best_cut)
            current_start = best_cut

        if not cuts or cuts[-1] < total_samples:
            cuts.append(total_samples)

        return cuts

    def _transcribe_chunked(
        self,
        path_obj: Path,
        language: str = "pt",
    ) -> TranscriptionResult:
        """Transcreve arquivos > 24 MB fatiando o áudio no silêncio com Silero VAD."""
        logger.info(
            f"Arquivo '{path_obj.name}' excede o limite da Groq (25 MB). "
            "Iniciando particionamento inteligente via Silero VAD..."
        )
        from faster_whisper.audio import decode_audio
        from faster_whisper.vad import VadOptions, get_speech_timestamps

        sample_rate = 16000
        audio_array = decode_audio(str(path_obj), sampling_rate=sample_rate)
        total_samples = len(audio_array)
        total_duration = round(total_samples / sample_rate, 2)

        speech_timestamps = get_speech_timestamps(audio_array, VadOptions())
        cut_points = self._calculate_cut_points(
            total_samples=total_samples,
            sample_rate=sample_rate,
            speech_timestamps=speech_timestamps,
            target_seconds=600,  # ~10 minutos por chunk
        )

        client = self._get_client()
        all_segments: list[SegmentData] = []
        text_parts: list[str] = []
        detected_language = language

        start_idx = 0
        for i, cut_idx in enumerate(cut_points):
            chunk_samples = audio_array[start_idx:cut_idx]
            offset_sec = round(start_idx / sample_rate, 2)
            chunk_wav = _audio_chunk_to_wav_bytes(
                chunk_samples, sample_rate=sample_rate
            )

            duration_sec = len(chunk_samples) / sample_rate
            logger.info(
                f"Enviando chunk {i + 1}/{len(cut_points)} "
                f"({duration_sec:.1f}s, offset={offset_sec}s) para a Groq..."
            )

            response = client.audio.transcriptions.create(
                file=(f"chunk_{i}.wav", chunk_wav),
                model=self.model,
                response_format="verbose_json",
                language=language,
            )

            c_text, c_segments, c_lang, _ = self._parse_groq_response(
                response,
                offset_seconds=offset_sec,
                default_language=language,
            )

            if c_text:
                text_parts.append(c_text)
            all_segments.extend(c_segments)
            detected_language = c_lang or detected_language
            start_idx = cut_idx

        full_text = " ".join(text_parts)
        logger.info(
            f"Transcrição particionada Groq concluída: {len(all_segments)} segmentos, "
            f"duração total={total_duration}s."
        )

        return TranscriptionResult(
            text=full_text,
            segments=all_segments,
            language=detected_language,
            duration=total_duration,
        )

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

        file_size = path_obj.stat().st_size

        # Se o arquivo for maior que 24 MB, utiliza particionamento VAD
        if file_size > GROQ_MAX_FILE_SIZE_BYTES:
            return self._transcribe_chunked(path_obj=path_obj, language=language)

        client = self._get_client()
        logger.info(
            f"Enviando áudio '{path_obj.name}' ({file_size / (1024 * 1024):.1f} MB) "
            f"para a Groq com modelo {self.model}..."
        )

        with open(path_obj, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                file=(path_obj.name, audio_file),
                model=self.model,
                response_format="verbose_json",
                language=language,
            )

        text, segments, detected_language, duration = self._parse_groq_response(
            response=response,
            offset_seconds=0.0,
            default_language=language,
        )

        logger.info(
            f"Transcrição Groq concluída com sucesso: {len(segments)} segmentos."
        )

        return TranscriptionResult(
            text=text,
            segments=segments,
            language=detected_language,
            duration=duration,
        )
