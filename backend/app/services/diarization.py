from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class DiarizationError(Exception):
    pass

# Dataclass para representar um segmento de diarização e manter o serviço independente
# frozen=true torna a classe imutável
# slots=true permite apenas a atribuição de valores aos atributos já definidos
@dataclass(frozen=True, slots=True)
class DiarizationSegment:
    speaker: str
    start_time: float
    end_time: float

# Interface para provedores de diarização. 
# todo provedor deve implementar o método diarize.
# recebe um caminho de arquivo de áudio e retorna um iterável de segmentos diarizados.
class DiarizationProvider(ABC):
    @abstractmethod
    def diarize(self, audio_path: Path) -> Iterable[DiarizationSegment]:
        pass


class DiarizationService:
    def __init__(self, provider: DiarizationProvider) -> None:
        self._provider = provider

    # método para realizar a diarização de um arquivo de áudio
    def diarize(self, audio_path: str | Path) -> list[DiarizationSegment]:
        # Recebe os parâmetros e valida o comportamento esperado
        path = Path(audio_path)
        if not path.is_file():
            raise FileNotFoundError(f"Arquivo de áudio não encontrado: {path}")

        try:
            provider_segments = list(self._provider.diarize(path))
        except DiarizationError:
            raise
        except Exception as exc:
            raise DiarizationError(
                "Falha ao executar o provider de diarização"
            ) from exc

        if not provider_segments:
            raise DiarizationError("O provider não retornou segmentos de diarização")

        segments = [self._validate_segment(item) for item in provider_segments]
        # ordena os segmentos por start_time, end_time e speaker para garantir consistência na saída
        segments.sort(key=lambda item: (item.start_time, item.end_time, item.speaker))

        # os speakers são armazenados em um dicionário 
        # para garantir a unicidade e consistência dos alias associados aos falantes
        speakers: dict[str, str] = {}
        # o resultado final é uma lista de segmentos de diarização com os 
        # speakers renomeados para os alias SPEAKER_00, SPEAKER_01, etc.
        result: list[DiarizationSegment] = []
        for segment in segments:
            # aqui setdefault é usado para retornar o valor existente se o speaker já estiver no dicionário
            # ou adicionar um novo speaker com o alias SPEAKER_XX se não estiver presente
            speaker = speakers.setdefault(
                segment.speaker,
                f"SPEAKER_{len(speakers):02d}",
            )
            result.append(
                DiarizationSegment(
                    speaker=speaker,
                    start_time=segment.start_time,
                    end_time=segment.end_time,
                )
            )

        # retorna a lista de segmentos de diarização com os speakers renomeados
        return result

    # metodo para validar os segmentos retornados pelo provider, 
    # garantindo que sejam instâncias de DiarizationSegment e que seus campos estejam corretos.
    @staticmethod
    def _validate_segment(segment: object) -> DiarizationSegment:
        if not isinstance(segment, DiarizationSegment):
            raise DiarizationError(
                "O provider deve retornar instâncias de DiarizationSegment"
            )

        try:
            speaker = segment.speaker.strip()
            start_time = float(segment.start_time)
            end_time = float(segment.end_time)
        except (AttributeError, TypeError, ValueError) as exc:
            raise DiarizationError(
                "O segmento possui campos com tipos inválidos"
            ) from exc

        if not speaker:
            raise DiarizationError("O speaker do segmento não pode ser vazio")
        if not math.isfinite(start_time) or not math.isfinite(end_time):
            raise DiarizationError("Os timestamps do segmento devem ser finitos")
        if start_time < 0 or end_time <= start_time:
            raise DiarizationError(
                "Os timestamps devem respeitar 0 <= start_time < end_time"
            )

        # retorna o segmento válido como uma instância de DiarizationSegment
        return DiarizationSegment(
            speaker=speaker,
            start_time=start_time,
            end_time=end_time,
        )
