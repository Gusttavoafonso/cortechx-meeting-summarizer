from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from app.core.config import settings


class DiarizationError(Exception):
    pass


class DiarizationAssociationError(DiarizationError):
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


# Implementação do provedor de diarização usando a biblioteca Pyannote.
# o modelo escolhido é "pyannote/speaker-diarization-community-1"
# e requer um token de autenticação do Hugging Face.
class PyannoteDiarizationProvider(DiarizationProvider):
    def __init__(
        self,
        token: str | None = None,
        pipeline: Any | None = None,
    ) -> None:
        # token e opcional para permitir a configuracao pelo arquivo .env
        self._token = token
        # pipeline pode ser injetado nos testes sem carregar o modelo real
        self._pipeline = pipeline

    # executa o Pyannote e converte o resultado para segmentos internos
    def diarize(self, audio_path: Path) -> list[DiarizationSegment]:
        try:
            output = self._get_pipeline()(str(audio_path))
            # diarizacao exclusiva evita sobreposicao entre speakers
            annotation = output.exclusive_speaker_diarization

            return [
                DiarizationSegment(
                    speaker=str(speaker),
                    start_time=float(turn.start),
                    end_time=float(turn.end),
                )
                for turn, _, speaker in annotation.itertracks(yield_label=True)
            ]
        except DiarizationError:
            raise
        except Exception as exc:
            raise DiarizationError("Falha ao executar o Pyannote") from exc

    # carrega o modelo apenas na primeira chamada de diarizacao
    def _get_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline

        token = self._token or self._get_configured_token()
        try:
            from pyannote.audio import Pipeline

            self._pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-community-1",
                token=token,
            )
        except Exception as exc:
            raise DiarizationError("Falha ao carregar o modelo do Pyannote") from exc

        if self._pipeline is None:
            raise DiarizationError("Não foi possível carregar o modelo do Pyannote")

        return self._pipeline

    @staticmethod
    # busca o token configurado para baixar o modelo do Hugging Face
    def _get_configured_token() -> str:
        if settings.huggingface_token is None:
            raise DiarizationError("HUGGINGFACE_TOKEN não configurado")

        token = settings.huggingface_token.get_secret_value().strip()
        if not token:
            raise DiarizationError("HUGGINGFACE_TOKEN não configurado")

        return token


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
        # ordena os segmentos por timestamp e speaker
        segments.sort(key=lambda item: (item.start_time, item.end_time, item.speaker))

        # os speakers são armazenados em um dicionário
        # para garantir a unicidade e consistência dos alias associados aos falantes
        speakers: dict[str, str] = {}
        # o resultado final é uma lista de segmentos de diarização com os
        # speakers renomeados para os alias SPEAKER_00, SPEAKER_01, etc.
        result: list[DiarizationSegment] = []
        for segment in segments:
            # reutiliza ou cria um alias consistente para o speaker
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
    # garantindo campos válidos no segmento.
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
