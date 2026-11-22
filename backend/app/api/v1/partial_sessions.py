"""Authenticated transport for provisional transcripts, separate from meetings."""

import time
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from redis.exceptions import RedisError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.partial_session import PartialSession
from app.models.user import User
from app.services import partial_stream as transport
from app.workers.partial_job import consume_partial_session

router = APIRouter(dependencies=[Depends(get_current_user)])
ACTIVE = ("recording", "finishing")


class StartPartial(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    provider: Literal["local"] = "local"
    language: Literal["pt", "en", "es", "auto"] = "pt"


class FinishPartial(BaseModel):
    chunk_count: int = Field(ge=0, le=7200)


def _owned(session_id: str, user_id: int) -> PartialSession:
    with SessionLocal() as db:
        row = db.get(PartialSession, session_id)
        if row is None or row.user_id != user_id or row.state == "cancelled":
            raise HTTPException(404, "Sessão parcial não encontrada.")
        return row


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _snapshot(row: PartialSession, after: int = -1) -> dict:
    return {
        "id": row.id, "state": row.state, "revision": row.revision,
        "text": row.text if row.revision > after else None,
        "processed_seconds": row.processed_seconds, "error": row.error,
        "provider": row.provider, "language": row.language,
    }


@router.post("", status_code=201)
def start_partial(payload: StartPartial, user: User = Depends(get_current_user)) -> dict:
    if settings.CELERY_TASK_ALWAYS_EAGER:
        raise HTTPException(503, "Parciais exigem worker Celery, sem modo eager.")
    session_id = str(payload.id)
    with SessionLocal() as db:
        existing = db.get(PartialSession, session_id)
        if existing is not None:
            if existing.user_id != user.id:
                raise HTTPException(404, "Sessão parcial não encontrada.")
            if existing.state == "cancelled":
                raise HTTPException(
                    410, "ID de sessão cancelada não pode ser reutilizado."
                )
            requested = (payload.provider, payload.language)
            if (existing.provider, existing.language) != requested:
                raise HTTPException(409, "ID reutilizado com outras opções.")
            return _snapshot(existing)
        count = db.scalar(select(func.count()).select_from(PartialSession).where(
            PartialSession.user_id == user.id, PartialSession.state.in_(ACTIVE)
        ))
        if count >= 4:
            raise HTTPException(429, "Encerre as sessões parciais anteriores.")
        row = PartialSession(
            id=session_id, user_id=user.id, provider=payload.provider,
            language=payload.language,
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, "Sessão já criada; consulte o mesmo ID.") from exc
        db.refresh(row)
        response = _snapshot(row)
    try:
        transport.initialize(session_id)
        consume_partial_session.apply_async(
            args=[session_id], queue="partial_transcription", expires=90
        )
    except Exception as exc:
        with SessionLocal() as db:
            db.execute(update(PartialSession).where(
                PartialSession.id == session_id, PartialSession.state.in_(ACTIVE)
            ).values(
                state="failed", error="Não foi possível iniciar o worker de parciais.",
                revision=PartialSession.revision + 1,
            ))
            db.commit()
        try:
            transport.purge(session_id)
        except RedisError:
            pass
        raise HTTPException(503, "Parciais indisponíveis; gravação final preservada.") from exc
    return response


def _append(session_id: str, user_id: int, sequence: int, data: bytes) -> dict:
    row = _owned(session_id, user_id)
    if row.state == "failed":
        raise HTTPException(409, row.error or "Sessão parcial encerrada.")
    try:
        result = transport.append(session_id, sequence, data)
    except RedisError as exc:
        raise HTTPException(503, "Transporte de parciais indisponível.") from exc
    if result < 0:
        raise HTTPException(-result, "Chunk fora de ordem, conflitante ou limite excedido.")
    return {"next_sequence": result}


@router.put("/{session_id}/chunks/{sequence}")
async def put_chunk(
    session_id: UUID, sequence: int, request: Request,
    user: User = Depends(get_current_user),
) -> dict:
    await run_in_threadpool(_owned, str(session_id), user.id)
    if not 0 <= sequence < 7200:
        raise HTTPException(400, "Sequência inválida.")
    # No File/Form parameters: authentication precedes reading the raw Blob.
    body = bytearray()
    async for part in request.stream():
        if len(body) + len(part) > transport.MAX_CHUNK:
            raise HTTPException(413, "Chunk excede 1 MiB.")
        body.extend(part)
    if not body:
        raise HTTPException(400, "Chunk vazio.")
    if sequence == 0 and not body.startswith(b"\x1a\x45\xdf\xa3"):
        raise HTTPException(415, "Parciais exigem WebM/Opus com cabeçalho inicial.")
    return await run_in_threadpool(
        _append, str(session_id), user.id, sequence, bytes(body)
    )


@router.post("/{session_id}/finish")
def finish_partial(
    session_id: UUID, payload: FinishPartial, user: User = Depends(get_current_user)
) -> dict:
    row = _owned(str(session_id), user.id)
    if row.state in ("completed", "failed"):
        return _snapshot(row)
    try:
        result = transport.finish(row.id, payload.chunk_count)
    except RedisError as exc:
        raise HTTPException(503, "Transporte de parciais indisponível.") from exc
    if result < 0:
        raise HTTPException(
            -result, "Finalize somente após confirmar todos os chunks."
        )
    with SessionLocal() as db:
        db.execute(update(PartialSession).where(
            PartialSession.id == row.id, PartialSession.state == "recording"
        ).values(state="finishing", revision=PartialSession.revision + 1))
        db.commit()
    return _snapshot(_owned(row.id, user.id))


@router.get("/{session_id}")
def poll_partial(
    session_id: UUID, after: int = Query(-1, ge=-1),
    user: User = Depends(get_current_user),
) -> dict:
    row = _owned(str(session_id), user.id)
    if row.state in ACTIVE:
        try:
            with transport.client() as redis:
                meta, _, _, lock = transport.keys(row.id)
                info = redis.hgetall(meta)
                stale = not info or time.time() - float(info.get(b"heartbeat", 0)) > 300
                waiting = not redis.exists(lock) and (
                    datetime.now(timezone.utc) - _as_utc(row.created_at)
                ).total_seconds() > 90
                if not stale and not waiting and row.state == "recording":
                    transport.touch_client(row.id)
            if stale or waiting:
                with SessionLocal() as db:
                    db.execute(update(PartialSession).where(
                        PartialSession.id == row.id, PartialSession.state.in_(ACTIVE)
                    ).values(state="failed", error="Worker parcial indisponível ou expirado.",
                             revision=PartialSession.revision + 1))
                    db.commit()
                transport.purge(row.id)
                row = _owned(row.id, user.id)
        except RedisError as exc:
            raise HTTPException(503, "Transporte de parciais indisponível.") from exc
    return _snapshot(row, after)


@router.delete("/{session_id}", status_code=204)
def cancel_partial(session_id: UUID, user: User = Depends(get_current_user)) -> None:
    # Retain only a tombstone: no partial text, no audio. A late start/provider
    # cannot recreate this session or persist after cancellation.
    for attempt in range(2):
        with SessionLocal() as db:
            row = db.get(PartialSession, str(session_id))
            if row is not None and row.user_id != user.id:
                raise HTTPException(404, "Sessão parcial não encontrada.")
            if row is None:
                row = PartialSession(id=str(session_id), user_id=user.id,
                                     provider="local", language="auto")
                db.add(row)
            row.state = "cancelled"
            row.text = ""
            row.error = None
            row.processed_seconds = 0
            row.revision = (row.revision or 0) + 1
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                if attempt == 0:
                    continue
                raise
            break
    try:
        transport.purge(str(session_id))
    except RedisError:
        # The tombstone still blocks late persistence; Redis keys have a TTL.
        pass
