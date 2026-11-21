"""One long-lived task per recording; never one task per Blob."""

import logging
import re
import time
import wave
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import numpy as np
from sqlalchemy import update

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.partial_session import PartialSession
from app.services import partial_stream as transport
from app.services.incremental_audio import IncrementalWebMDecoder
from app.services.transcription.faster_whisper_service import FasterWhisperService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
ACTIVE = ("recording", "finishing")


def _save(session_id: str, **values) -> None:
    with SessionLocal() as db:
        result = db.execute(update(PartialSession).where(
            PartialSession.id == session_id, PartialSession.state.in_(ACTIVE)
        ).values(**values, revision=PartialSession.revision + 1,
                 updated_at=datetime.now(timezone.utc)))
        db.commit()
        if result.rowcount == 0:
            raise transport.StreamClosed("Sessão parcial encerrada")


def _pulse(redis, meta: str) -> None:
    if not redis.eval("""
if redis.call('EXISTS', KEYS[1]) == 0 then return 0 end
redis.call('HSET', KEYS[1], 'heartbeat', ARGV[1])
return 1
""", 1, meta, time.time()):
        raise transport.StreamClosed("Sessão cancelada")


def _provider() -> FasterWhisperService:
    # Partials are always local; final processing provider options are unrelated.
    return FasterWhisperService(
        model_size=settings.WHISPER_MODEL_SIZE,
        device=settings.WHISPER_DEVICE,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
    )


def _reconcile(tokens: list, result, window) -> list:
    """Replace the previous provisional overlap rather than append it twice.

    Existing providers expose segment times, not word times. Word positions are
    interpolated inside segments only to trim this provisional boundary. The
    final transcript is independent and remains authoritative.
    """
    kept = [token for token in tokens if token[0] < window.start_seconds]
    fresh = []
    segments = result.segments or []
    if not segments:
        parts = [(0.0, window.end_seconds - window.start_seconds, result.text)]
    else:
        parts = [(s.start, s.end, s.text) for s in segments]
    for start, end, text in parts:
        words = text.split()
        start = max(0.0, float(start or 0))
        duration = window.end_seconds - window.start_seconds
        end = min(duration, float(end if end is not None else duration))
        for index, word in enumerate(words):
            position = window.start_seconds + start + (
                (index + 0.5) * max(0.0, end - start) / max(1, len(words))
            )
            fresh.append((position, word))
    def normalize(word: str) -> str:
        return re.sub(r"\W+", "", word.casefold())
    # A word straddling the cut may have drifted across segment boundaries.
    if tokens and window.start_seconds > 0:
        for count in range(min(8, len(kept), len(fresh)), 0, -1):
            left = [normalize(item[1]) for item in kept[-count:]]
            right = [normalize(item[1]) for item in fresh[:count]]
            if left == right and any(left):
                fresh = fresh[count:]
                break
    return kept + fresh


@celery_app.task(
    name="app.workers.partial_job.consume_partial_session",
    ignore_result=True, acks_late=False, time_limit=3 * 3600,
)
def consume_partial_session(session_id: str) -> None:
    meta, queue, _, lock = transport.keys(session_id)
    token = str(uuid4())
    with transport.client() as redis:
        if not redis.set(lock, token, nx=True, ex=transport.TTL):
            return
        try:
            with SessionLocal() as db:
                row = db.get(PartialSession, session_id)
                if row is None or row.state not in ACTIVE:
                    return
                language = row.language
            provider = _provider()
            tokens = []
            decoder = IncrementalWebMDecoder(max_chunk_bytes=transport.MAX_CHUNK)
            with TemporaryDirectory(prefix="partial-audio-") as temporary:
                path = Path(temporary) / "window.wav"
                decoded = decoder.iter_windows(transport.chunks(session_id, redis))
                with closing(decoded) as windows:
                    for window in windows:
                        if window.end_seconds > transport.MAX_SECONDS:
                            raise TimeoutError("Limite de duas horas excedido")
                        # Check cancellation before invoking any provider.
                        with SessionLocal() as db:
                            row = db.get(PartialSession, session_id)
                            if row is None or row.state not in ACTIVE:
                                raise transport.StreamClosed()
                        with wave.open(str(path), "wb") as output:
                            output.setnchannels(1)
                            output.setsampwidth(2)
                            output.setframerate(window.sample_rate)
                            pcm = (np.clip(window.samples, -1, 1) * 32767).astype("<i2")
                            output.writeframes(pcm.tobytes())
                        _pulse(redis, meta)
                        result = provider.transcribe(
                            path, language=None if language == "auto" else language
                        )
                        tokens = _reconcile(tokens, result, window)
                        _save(session_id, text=" ".join(word for _, word in tokens),
                              processed_seconds=window.end_seconds)
                        _pulse(redis, meta)
            _save(session_id, state="completed")
        except Exception:
            logger.exception(
                "Partial transcription stopped for session %s", session_id
            )
            try:
                _save(session_id, state="failed", error=(
                    "Falha no decoder/transcritor local parcial. "
                    "A gravação e o processamento final continuam disponíveis."
                ))
            except transport.StreamClosed:
                pass
        finally:
            # Do not recreate metadata deleted by cancellation. Keep hashes for
            # idempotent acknowledgements until their existing TTL expires.
            redis.eval("""
redis.call('DEL', KEYS[2])
if redis.call('EXISTS', KEYS[1]) == 1 then
  redis.call('HSET', KEYS[1], 'state', 'closed', 'queued', 0)
end
if redis.call('GET', KEYS[3]) == ARGV[1] then redis.call('DEL', KEYS[3]) end
""", 3, meta, queue, lock, token)
