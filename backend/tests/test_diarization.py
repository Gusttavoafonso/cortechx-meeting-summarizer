from pathlib import Path

import pytest
from app.services.diarization import (
    DiarizationError,
    DiarizationProvider,
    DiarizationSegment,
    DiarizationService,
)

# define um provider falso para testes, que retorna os segmentos fornecidos ou lança um erro
class FakeDiarizationProvider(DiarizationProvider):
    def __init__(
        self,
        segments: list[object] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.segments = segments or []
        self.error = error
        self.calls = 0

    def diarize(self, audio_path: Path) -> list[object]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.segments


@pytest.fixture
def audio_path(tmp_path: Path) -> Path:
    path = tmp_path / "meeting.wav"
    path.write_bytes(b"audio")
    return path


# garante que o serviço ordena os segmentos e mantém o mesmo ID para a mesma voz
def test_diarize_orders_segments_and_normalizes_speakers(audio_path: Path) -> None:
    provider = FakeDiarizationProvider(
        [
            DiarizationSegment("guest", 4, 8),
            DiarizationSegment("host", 0, 4),
            DiarizationSegment("host", 8, 10),
        ]
    )

    result = DiarizationService(provider).diarize(audio_path)

    assert result == [
        DiarizationSegment("SPEAKER_00", 0.0, 4.0),
        DiarizationSegment("SPEAKER_01", 4.0, 8.0),
        DiarizationSegment("SPEAKER_00", 8.0, 10.0),
    ]


# garante que um arquivo inexistente é rejeitado antes de chamar o provider
def test_diarize_rejects_missing_audio_file(tmp_path: Path) -> None:
    provider = FakeDiarizationProvider([DiarizationSegment("host", 0, 1)])

    with pytest.raises(FileNotFoundError):
        DiarizationService(provider).diarize(tmp_path / "missing.wav")

    assert provider.calls == 0


# garante que a ausência de segmentos retornados pelo provider é tratada como erro
def test_diarize_rejects_empty_provider_result(audio_path: Path) -> None:
    service = DiarizationService(FakeDiarizationProvider())

    with pytest.raises(DiarizationError, match="não retornou segmentos"):
        service.diarize(audio_path)


# garante que uma falha inesperada do provider é encapsulada pela exceção do serviço
def test_diarize_wraps_provider_failure(audio_path: Path) -> None:
    service = DiarizationService(FakeDiarizationProvider(error=RuntimeError("offline")))

    with pytest.raises(DiarizationError) as error:
        service.diarize(audio_path)

    assert isinstance(error.value.__cause__, RuntimeError)


# garante que um início negativo não é aceito
def test_diarize_rejects_negative_start_time(audio_path: Path) -> None:
    service = DiarizationService(
        FakeDiarizationProvider([DiarizationSegment("host", -0.1, 1)])
    )

    with pytest.raises(DiarizationError, match="0 <= start_time < end_time"):
        service.diarize(audio_path)


# garante que um segmento sem duração, com início igual ao fim, não é aceito
def test_diarize_rejects_equal_start_and_end_times(audio_path: Path) -> None:
    service = DiarizationService(
        FakeDiarizationProvider([DiarizationSegment("host", 1, 1)])
    )

    with pytest.raises(DiarizationError, match="0 <= start_time < end_time"):
        service.diarize(audio_path)


# garante que o fim anterior ao início não é aceito
def test_diarize_rejects_end_time_before_start_time(audio_path: Path) -> None:
    service = DiarizationService(
        FakeDiarizationProvider([DiarizationSegment("host", 3, 2)])
    )

    with pytest.raises(DiarizationError, match="0 <= start_time < end_time"):
        service.diarize(audio_path)


# garante que timestamps não numéricos ou infinitos não contaminam o resultado
@pytest.mark.parametrize(
    "segment",
    [
        DiarizationSegment("host", float("nan"), 1),
        DiarizationSegment("host", 0, float("inf")),
    ],
)
def test_diarize_rejects_non_finite_timestamps(
    audio_path: Path,
    segment: DiarizationSegment,
) -> None:
    service = DiarizationService(FakeDiarizationProvider([segment]))

    with pytest.raises(DiarizationError, match="devem ser finitos"):
        service.diarize(audio_path)


# garante que segmentos sem identificação de speaker são rejeitados
def test_diarize_rejects_empty_speaker(audio_path: Path) -> None:
    service = DiarizationService(
        FakeDiarizationProvider([DiarizationSegment("   ", 0, 1)])
    )

    with pytest.raises(DiarizationError, match="speaker.*vazio"):
        service.diarize(audio_path)


# garante que o provider não possa retornar objetos fora do contrato definido
def test_diarize_rejects_invalid_provider_segment_type(audio_path: Path) -> None:
    service = DiarizationService(FakeDiarizationProvider([{"speaker": "host"}]))

    with pytest.raises(DiarizationError, match="DiarizationSegment"):
        service.diarize(audio_path)
