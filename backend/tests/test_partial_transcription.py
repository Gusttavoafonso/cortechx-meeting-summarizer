from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from app.services.incremental_audio import (
    SAMPLE_RATE,
    STEP_SAMPLES,
    WINDOW_SAMPLES,
    AudioWindow,
    IncrementalWebMDecoder,
)
from app.services.transcription.base import SegmentData, TranscriptionResult
from app.services.transcription.faster_whisper_service import (
    _MODEL_CACHE,
    FasterWhisperService,
)
from app.workers.partial_job import _reconcile


def test_reconcile_deduplicates_overlap_and_normalizes_punctuation():
    prev_tokens = [
        (0.5, "Olá,"),
        (1.5, "pessoal."),
        (3.2, "Vamos"),
        (4.1, "começar!"),
        (5.0, "Agora"),
    ]
    window = AudioWindow(
        samples=np.zeros(WINDOW_SAMPLES, dtype=np.float32),
        start_sample=4 * SAMPLE_RATE,
    )
    result = TranscriptionResult(
        text="agora vamos continuar o projeto",
        segments=[
            SegmentData(start=0.0, end=2.5, text="agora, vamos continuar o projeto"),
        ],
        language="pt",
        duration=6.0,
    )

    merged = _reconcile(prev_tokens, result, window)
    words = [word for _, word in merged]
    assert words == ["Olá,", "pessoal.", "Vamos", "agora,", "vamos", "continuar", "o", "projeto"]

    # Testa match exato na borda com pontuação/caixa diferentes
    prev_tokens_2 = [
        (1.0, "Arquitetura"),
        (2.0, "distribuída."),
        (3.2, "Whisper,"),
        (3.8, "local!"),
    ]
    result_2 = TranscriptionResult(
        text="whisper local com chunks",
        segments=[
            SegmentData(start=0.0, end=3.0, text="whisper local com chunks"),
        ],
        language="pt",
        duration=6.0,
    )
    merged_2 = _reconcile(prev_tokens_2, result_2, window)
    assert [w for _, w in merged_2] == [
        "Arquitetura",
        "distribuída.",
        "Whisper,",
        "local!",
        "com",
        "chunks",
    ]


def test_incremental_decoder_window_constants_and_validation():
    assert SAMPLE_RATE == 16_000
    assert WINDOW_SAMPLES == 6 * SAMPLE_RATE
    assert STEP_SAMPLES == 4 * SAMPLE_RATE
    assert WINDOW_SAMPLES - STEP_SAMPLES == 2 * SAMPLE_RATE

    with pytest.raises(ValueError):
        IncrementalWebMDecoder(max_chunk_bytes=0)
    with pytest.raises(ValueError):
        IncrementalWebMDecoder(max_chunk_bytes=-10)

    decoder = IncrementalWebMDecoder(max_chunk_bytes=2048)
    assert decoder.max_chunk_bytes == 2048


def test_faster_whisper_transcribe_array_uses_expected_params(monkeypatch):
    calls: list[tuple[object, dict]] = []

    class FakeModel:
        def transcribe(self, source, **kwargs):
            calls.append((source, kwargs))
            seg = SimpleNamespace(start=0.1, end=1.2, text=" Olá mundo ")
            info = SimpleNamespace(duration=1.2, language="pt")
            return iter([seg]), info

    cache_key = ("tiny-test", "cpu", "int8")
    _MODEL_CACHE[cache_key] = FakeModel()
    try:
        service = FasterWhisperService(
            model_size="tiny-test",
            device="cpu",
            compute_type="int8",
            vad_filter=True,
        )
        audio = np.zeros(1600, dtype=np.float32)
        result = service.transcribe_array(
            audio,
            language="pt",
            beam_size=1,
            condition_on_previous_text=False,
        )

        assert len(calls) == 1
        passed_source, passed_kwargs = calls[0]
        assert passed_source is audio
        assert passed_kwargs["language"] == "pt"
        assert passed_kwargs["beam_size"] == 1
        assert passed_kwargs["condition_on_previous_text"] is False
        assert passed_kwargs["vad_filter"] is True
        assert result.text == "Olá mundo"
        assert result.segments == [SegmentData(start=0.1, end=1.2, text="Olá mundo")]
    finally:
        _MODEL_CACHE.pop(cache_key, None)
