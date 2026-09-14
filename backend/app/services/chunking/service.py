from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Sequence

from app.schemas.chunk import Chunk, ChunkingConfig

if TYPE_CHECKING:
    from app.models.transcript import Transcript
    from app.models.transcript_segment import TranscriptSegment


class ChunkingService:
    """Serviço responsável pela divisão determinística de transcrições em chunks."""

    def __init__(self, default_config: ChunkingConfig | None = None) -> None:
        self.config = default_config or ChunkingConfig()

    def split(
        self,
        transcript: Transcript | Sequence[TranscriptSegment] | str | None,
        config: ChunkingConfig | None = None,
    ) -> list[Chunk]:
        """Divide uma transcrição em uma lista ordenada de chunks.

        Aceita:
        - Transcript (modelo SQLAlchemy com relação .segments ou .content/.raw_text)
        - Sequence[TranscriptSegment] (lista de segmentos diarizados)
        - str (texto puro de transcrição como fallback)
        """
        if transcript is None:
            return []

        active_config = config or self.config

        # 1. Se for string pura
        if isinstance(transcript, str):
            clean_text = transcript.strip()
            if not clean_text:
                return []
            return self._split_raw_text(clean_text, active_config)

        # 2. Se for objeto Transcript com segmentos ou texto
        if hasattr(transcript, "segments"):
            segments: Sequence[TranscriptSegment] = (
                getattr(transcript, "segments") or []
            )
            if segments:
                return self._split_segments(segments, active_config)

            # Fallback para texto bruto do Transcript caso não haja segmentos
            raw_text = getattr(transcript, "content", None) or getattr(
                transcript, "raw_text", None
            )
            if raw_text and str(raw_text).strip():
                return self._split_raw_text(str(raw_text).strip(), active_config)
            return []

        # 3. Se for uma sequência de segmentos
        if isinstance(transcript, Sequence):
            if not transcript:
                return []
            return self._split_segments(transcript, active_config)

        return []

    def _split_segments(
        self,
        segments: Sequence[Any],
        config: ChunkingConfig,
    ) -> list[Chunk]:
        """Agrupa TranscriptSegments em chunks respeitando limites e overlap."""
        # Ordenação cronológica determinística (start_time, end_time, id)
        sorted_segments = sorted(
            segments,
            key=lambda s: (
                getattr(s, "start_time", None)
                if getattr(s, "start_time", None) is not None
                else 0.0,
                getattr(s, "end_time", None)
                if getattr(s, "end_time", None) is not None
                else 0.0,
                getattr(s, "id", 0) or 0,
            ),
        )

        total_segments = len(sorted_segments)
        if total_segments == 0:
            return []

        chunks: list[Chunk] = []
        current_start_idx = 0
        chunk_index = 0

        while current_start_idx < total_segments:
            chunk_segments: list[Any] = []
            chunk_start_time: float | None = getattr(
                sorted_segments[current_start_idx], "start_time", None
            )
            accumulated_tokens = 0
            end_idx = current_start_idx

            for i in range(current_start_idx, total_segments):
                seg = sorted_segments[i]
                formatted_seg = self._format_segment(seg)
                seg_tokens = self._estimate_tokens(formatted_seg)
                seg_end = getattr(seg, "end_time", None)

                # Calcular duração potencial do chunk
                duration: float | None = None
                if chunk_start_time is not None and seg_end is not None:
                    duration = seg_end - chunk_start_time

                # Verificar se adicionar este segmento ultrapassa os limites
                # (Sempre incluímos pelo menos 1 segmento para evitar loop)
                exceeds_duration = (
                    duration is not None and duration > config.max_duration_seconds
                )
                exceeds_tokens = (accumulated_tokens + seg_tokens) > config.max_tokens

                if chunk_segments and (exceeds_duration or exceeds_tokens):
                    break

                chunk_segments.append(seg)
                accumulated_tokens += seg_tokens
                end_idx = i + 1

            if not chunk_segments:
                chunk_segments = [sorted_segments[current_start_idx]]
                end_idx = current_start_idx + 1

            # Montagem do Chunk atual
            first_seg = chunk_segments[0]
            formatted_lines = [self._format_segment(s) for s in chunk_segments]
            chunk_text = "\n".join(formatted_lines)

            # Encontrar o maior end_time real entre os segmentos do chunk
            valid_end_times = [
                getattr(s, "end_time", None)
                for s in chunk_segments
                if getattr(s, "end_time", None) is not None
            ]
            chunk_end_time: float | None = (
                max(valid_end_times) if valid_end_times else None
            )

            speakers: set[str] = set()
            for s in chunk_segments:
                spk = getattr(s, "speaker", None)
                if spk and str(spk).strip():
                    speakers.add(str(spk).strip())

            chunk_obj = Chunk(
                index=chunk_index,
                text=chunk_text,
                start_time=getattr(first_seg, "start_time", None),
                end_time=chunk_end_time,
                speakers=sorted(list(speakers)),
                segment_count=len(chunk_segments),
                estimated_tokens=self._estimate_tokens(chunk_text),
            )
            chunks.append(chunk_obj)
            chunk_index += 1

            # Se alcançamos o final dos segmentos, encerramos
            if end_idx >= total_segments:
                break

            # Determinar o ponto de partida do próximo chunk aplicando o OVERLAP
            next_start_idx = self._calculate_next_start_index(
                sorted_segments=sorted_segments,
                current_start_idx=current_start_idx,
                end_idx=end_idx,
                chunk_end_time=chunk_end_time,
                config=config,
            )

            # Garantir progresso estrito para frente
            if next_start_idx <= current_start_idx:
                next_start_idx = current_start_idx + 1

            current_start_idx = next_start_idx

        return chunks

    def _calculate_next_start_index(
        self,
        sorted_segments: Sequence[Any],
        current_start_idx: int,
        end_idx: int,
        chunk_end_time: float | None,
        config: ChunkingConfig,
    ) -> int:
        """Calcula o índice do próximo chunk garantindo o overlap configurado."""
        if config.overlap_duration_seconds <= 0 and config.overlap_segments <= 0:
            return end_idx

        # 1. Estratégia de overlap temporal
        if chunk_end_time is not None and config.overlap_duration_seconds > 0:
            target_time = max(0.0, chunk_end_time - config.overlap_duration_seconds)
            for candidate_idx in range(current_start_idx + 1, end_idx):
                seg_end = getattr(sorted_segments[candidate_idx], "end_time", None)
                seg_start = getattr(sorted_segments[candidate_idx], "start_time", None)

                if (seg_end is not None and seg_end > target_time) or (
                    seg_start is not None and seg_start >= target_time
                ):
                    return candidate_idx

            return end_idx

        # 2. Estratégia de overlap por quantidade de segmentos (fallback)
        overlap_count = max(1, config.overlap_segments)
        next_idx = max(current_start_idx + 1, end_idx - overlap_count)
        return next_idx

    def _split_raw_text(
        self,
        text: str,
        config: ChunkingConfig,
    ) -> list[Chunk]:
        """Fallback para divisão de texto puro quando não há TranscriptSegments."""
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]

        chunks: list[Chunk] = []
        current_paras: list[str] = []
        accumulated_tokens = 0
        chunk_index = 0

        for p in paragraphs:
            p_tokens = self._estimate_tokens(p)
            if current_paras and (accumulated_tokens + p_tokens > config.max_tokens):
                chunk_text = "\n\n".join(current_paras)
                chunks.append(
                    Chunk(
                        index=chunk_index,
                        text=chunk_text,
                        start_time=None,
                        end_time=None,
                        speakers=[],
                        segment_count=len(current_paras),
                        estimated_tokens=self._estimate_tokens(chunk_text),
                    )
                )
                chunk_index += 1

                # Overlap de texto: mantém o último parágrafo
                if len(current_paras) > 1 and config.overlap_segments > 0:
                    current_paras = [current_paras[-1]]
                    accumulated_tokens = self._estimate_tokens(current_paras[0])
                else:
                    current_paras = []
                    accumulated_tokens = 0

            current_paras.append(p)
            accumulated_tokens += p_tokens

        if current_paras:
            chunk_text = "\n\n".join(current_paras)
            chunks.append(
                Chunk(
                    index=chunk_index,
                    text=chunk_text,
                    start_time=None,
                    end_time=None,
                    speakers=[],
                    segment_count=len(current_paras),
                    estimated_tokens=self._estimate_tokens(chunk_text),
                )
            )

        return chunks

    def _format_segment(self, segment: Any) -> str:
        """Formata fala no padrão [MM:SS] Speaker: fala ou [HH:MM:SS] Speaker: fala."""
        start_time = getattr(segment, "start_time", None)
        speaker = getattr(segment, "speaker", None)
        text = (getattr(segment, "text", "") or "").strip()

        time_tag = self._format_timestamp(start_time)
        speaker_tag = str(speaker).strip() if speaker and str(speaker).strip() else ""

        if time_tag and speaker_tag:
            return f"{time_tag} {speaker_tag}: {text}"
        elif time_tag:
            return f"{time_tag} {text}"
        elif speaker_tag:
            return f"{speaker_tag}: {text}"
        return text

    @staticmethod
    def _format_timestamp(seconds: float | None) -> str:
        """Converte segundos em string de timestamp [MM:SS] ou [HH:MM:SS]."""
        if seconds is None:
            return ""

        total_secs = max(0, int(math.floor(seconds)))
        hours = total_secs // 3600
        minutes = (total_secs % 3600) // 60
        secs = total_secs % 60

        if hours > 0:
            return f"[{hours:02d}:{minutes:02d}:{secs:02d}]"
        return f"[{minutes:02d}:{secs:02d}]"

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Estima a quantidade de tokens de forma conservadora para LLMs."""
        if not text:
            return 0
        words = text.split()
        word_estimate = int(len(words) * 1.4)
        char_estimate = int(len(text) / 3.8)
        return max(1, word_estimate, char_estimate)
