"""POC de decodificacao incremental de um unico WebM/Opus continuo.

Uso: ``IncrementalWebMDecoder().iter_windows(chunks)``; ``chunks`` fornece bytes
ordenados da mesma sessao MediaRecorder (normalmente Blobs de cerca de 1 segundo).
O primeiro chunk deve incluir o cabecalho WebM. Fronteiras de chunks podem cortar
qualquer elemento do container; nao se abre cada Blob como um arquivo separado.

O iterador de entrada deve bloquear enquanto aguarda dados e terminar somente no
fim da gravacao. Sua exaustao sinaliza EOF e faz o flush do decoder/resampler e da
ultima janela parcial, sem padding. Bytes vazios sao ignorados, nao sinalizam EOF.
O consumo e sincrono e sob demanda; nao usar diretamente no event loop. Ao parar
antes de EOF, fechar o gerador retornado (por exemplo, com contextlib.closing).

Memoria propria: um chunk comprimido de ate max_chunk_bytes, um buffer de 10s de
PCM e copias das janelas emitidas. PyAV usa um buffer de IO de 32 KiB. Alocacoes
internas de FFmpeg e janelas retidas pelo consumidor nao fazem parte desse limite.
Esta POC nao e um sandbox para containers arbitrarios ou maliciosos.

Compativel apenas com uma faixa Opus em WebM continuo, com cabecalho inicial e
chunks completos e ordenados da mesma sessao. Nao concatena gravacoes, recupera
chunks perdidos ou retoma apos EOF. O probing e os clusters WebM podem atrasar a
primeira emissao: timeslice de 1s nao garante latencia de 1s. Erros de entrada e de
PyAV sao propagados; nenhum flush parcial e prometido para arquivos corrompidos.
Timestamps usam contagem de amostras PCM desde zero, nao PTS do container ou tempo
de parede; lacunas/descontinuidades de PTS nao inserem silencio nesta POC.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

import av
import numpy as np
from numpy.typing import NDArray

SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 6 * SAMPLE_RATE
STEP_SAMPLES = 4 * SAMPLE_RATE
IO_BUFFER_BYTES = 32 * 1024


@dataclass(frozen=True)
class AudioWindow:
    """PCM mono float32 e intervalo [start_sample, end_sample) a 16 kHz.

    A janela possui sua propria copia das amostras. A ultima pode ter menos de
    10s e inclui overlap apenas se houver amostras novas desde a emissao anterior.
    """

    samples: NDArray[np.float32]
    start_sample: int
    sample_rate: int = SAMPLE_RATE

    @property
    def end_sample(self) -> int:
        return self.start_sample + self.samples.size

    @property
    def start_seconds(self) -> float:
        return self.start_sample / self.sample_rate

    @property
    def end_seconds(self) -> float:
        return self.end_sample / self.sample_rate


class _ChunkReader(io.RawIOBase):
    """IO nao seekable: leituras curtas preservam bytes sem acumular historico."""

    def __init__(self, chunks: Iterable[bytes], max_chunk_bytes: int) -> None:
        super().__init__()
        self._chunks = iter(chunks)
        self._max_chunk_bytes = max_chunk_bytes
        self._pending = memoryview(b"")

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def read(self, size: int = -1) -> bytes:
        if self.closed:
            raise ValueError("Leitura apos fechamento do stream")
        if size < 0:
            raise io.UnsupportedOperation("Leitura sem limite nao suportada")
        if size == 0:
            return b""
        while not self._pending:
            try:
                chunk = next(self._chunks)
            except StopIteration:
                return b""
            if not isinstance(chunk, bytes):
                raise TypeError("Cada chunk deve ser bytes imutaveis")
            if len(chunk) > self._max_chunk_bytes:
                raise ValueError("Chunk excede max_chunk_bytes")
            self._pending = memoryview(chunk)
        result = self._pending[:size].tobytes()
        self._pending = self._pending[len(result) :]
        return result

    def close(self) -> None:
        self._pending = memoryview(b"")
        self._chunks = iter(())
        super().close()


class IncrementalWebMDecoder:
    """Uma chamada de iter_windows cria um contexto PyAV para toda a sessao.

    Produz [0s,6s), [4s,10s), [8s,14s), ... e uma cauda parcial no EOF.
    O produtor continua dono do iterador de entrada e de seus recursos. Nao ha
    fila interna, thread, arquivo temporario ou integracao com providers.
    """

    def __init__(self, *, max_chunk_bytes: int = 1024 * 1024) -> None:
        if not isinstance(max_chunk_bytes, int) or max_chunk_bytes <= 0:
            raise ValueError("max_chunk_bytes deve ser um inteiro positivo")
        self.max_chunk_bytes = max_chunk_bytes

    def iter_windows(self, chunks: Iterable[bytes]) -> Iterator[AudioWindow]:
        """Decodifica uma sessao; exaurir o gerador faz o flush final.

        O array emitido tem o mesmo formato usado por decode_audio do
        faster-whisper e pelo helper WAV da Groq, sem chama-los ou modifica-los.
        Uma entrada vazia/sem cabecalho e invalida, nao uma sessao silenciosa.
        """
        pcm = np.empty(WINDOW_SAMPLES, dtype=np.float32)
        filled = 0
        start_sample = 0
        last_emitted_end = 0
        with _ChunkReader(chunks, self.max_chunk_bytes) as source:
            with av.open(
                source,
                mode="r",
                format="webm",
                buffer_size=IO_BUFFER_BYTES,
                options={
                    "probesize": str(IO_BUFFER_BYTES),
                    "analyzeduration": "1000000",
                },
            ) as container:
                audio_streams = container.streams.audio
                if len(audio_streams) != 1:
                    raise ValueError("Esperada exatamente uma faixa de audio Opus")
                stream = audio_streams[0]
                if stream.codec_context.name != "opus":
                    raise ValueError("Esta POC aceita somente WebM/Opus")
                for frame in self._resample(container, stream):
                    samples = frame.to_ndarray().reshape(-1).astype(np.float32) / 32768
                    offset = 0
                    while offset < samples.size:
                        count = min(WINDOW_SAMPLES - filled, samples.size - offset)
                        pcm[filled : filled + count] = samples[offset : offset + count]
                        filled += count
                        offset += count
                        if filled == WINDOW_SAMPLES:
                            last_emitted_end = start_sample + filled
                            yield AudioWindow(pcm.copy(), start_sample)
                            overlap = WINDOW_SAMPLES - STEP_SAMPLES
                            pcm[:overlap] = pcm[STEP_SAMPLES:]
                            filled = overlap
                            start_sample += STEP_SAMPLES
                if start_sample + filled > last_emitted_end:
                    yield AudioWindow(pcm[:filled].copy(), start_sample)

    @staticmethod
    def _resample(
        container: av.container.InputContainer, stream: av.audio.stream.AudioStream
    ) -> Iterator[av.AudioFrame]:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        # container.decode inclui os frames retidos pelo codec no EOF.
        for frame in container.decode(stream):
            frame.pts = None  # Timeline definida por amostras, sem remontar PTS.
            yield from resampler.resample(frame)
        yield from resampler.resample(None)
