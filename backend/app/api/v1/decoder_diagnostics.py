"""Diagnostico local da etapa A; sem persistencia ou processamento de reunioes."""

from collections.abc import Iterator
from contextlib import closing

import av
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.services.incremental_audio import SAMPLE_RATE, IncrementalWebMDecoder

MAX_CHUNKS = 120
MAX_CHUNK_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
# Margem de 1 MiB para boundaries e headers das partes multipart.
MAX_REQUEST_BYTES = MAX_TOTAL_BYTES + 1024 * 1024
MAX_DURATION_SECONDS = 90


def _require_debug() -> None:
    if not settings.DEBUG:
        raise HTTPException(404, "Diagnostico disponivel somente com APP_DEBUG=true.")


router = APIRouter(dependencies=[Depends(_require_debug), Depends(get_current_user)])


def _validate_webm_header(chunks: list[UploadFile]) -> None:
    # FFmpeg compartilha o demuxer Matroska/WebM: verificar DocType evita aceitar
    # Matroska generico apenas porque foi aberto com format="webm".
    header = bytearray()
    for chunk in chunks:
        header.extend(chunk.file.read(4096 - len(header)))
        chunk.file.seek(0)
        if len(header) == 4096:
            break

    def vint(offset: int, *, element_id: bool = False) -> tuple[int, int]:
        if offset >= len(header) or header[offset] == 0:
            raise ValueError("Cabecalho EBML incompleto ou invalido")
        width = 9 - header[offset].bit_length()
        end = offset + width
        if end > len(header) or (element_id and width > 4):
            raise ValueError("Cabecalho EBML excede o limite de 4 KiB")
        value = int.from_bytes(header[offset:end], "big")
        if not element_id:
            mask = (1 << (7 * width)) - 1
            value &= mask
            if value == mask:
                raise ValueError("Tamanho indefinido no cabecalho EBML")
        return value, end

    if header[:4] != b"\x1a\x45\xdf\xa3":
        raise ValueError("Primeiro chunk deve conter o cabecalho WebM")
    size, offset = vint(4)
    end = offset + size
    if end > len(header):
        raise ValueError("Cabecalho EBML incompleto ou maior que 4 KiB")
    doc_type = None
    while offset < end:
        element, offset = vint(offset, element_id=True)
        length, offset = vint(offset)
        if offset + length > end:
            raise ValueError("Elemento EBML fora do cabecalho")
        if element == 0x4282:
            doc_type = bytes(header[offset : offset + length])
        offset += length
    if doc_type != b"webm":
        raise ValueError("Container deve ter DocType WebM")


def _read_chunks(chunks: list[UploadFile]) -> Iterator[bytes]:
    for chunk in chunks:
        # Preserva exatamente cada Blob; nao concatena nem abre Blobs separados.
        yield chunk.file.read(MAX_CHUNK_BYTES + 1)


def _decode_chunks(chunks: list[UploadFile]) -> dict:
    """Validacao e decodificacao sincronas; executar somente no threadpool."""
    try:
        if not 1 <= len(chunks) <= MAX_CHUNKS:
            raise HTTPException(413, f"Envie de 1 a {MAX_CHUNKS} chunks ordenados.")
        total_bytes = 0
        for chunk in chunks:
            mime = (chunk.content_type or "").split(";", 1)[0].strip().lower()
            if mime not in {"audio/webm", "application/octet-stream", ""}:
                raise HTTPException(415, "Somente Blobs originais de audio WebM/Opus.")
            size = chunk.file.seek(0, 2)
            chunk.file.seek(0)
            if size == 0:
                raise HTTPException(400, "Chunks vazios nao sao aceitos.")
            if size > MAX_CHUNK_BYTES:
                raise HTTPException(413, "Cada chunk pode ter no maximo 1 MiB.")
            total_bytes += size
        if total_bytes > MAX_TOTAL_BYTES:
            raise HTTPException(413, "Upload excede o limite total de 16 MiB.")
        _validate_webm_header(chunks)

        windows = []
        end_sample = 0
        decoder = IncrementalWebMDecoder(max_chunk_bytes=MAX_CHUNK_BYTES)
        with closing(decoder.iter_windows(_read_chunks(chunks))) as decoded:
            for index, window in enumerate(decoded):
                if window.end_sample > MAX_DURATION_SECONDS * SAMPLE_RATE:
                    raise HTTPException(413, "Audio decodificado excede 90 segundos.")
                end_sample = window.end_sample
                windows.append(
                    {
                        "index": index,
                        "start_sample": window.start_sample,
                        "end_sample": window.end_sample,
                        "start_seconds": window.start_seconds,
                        "end_seconds": window.end_seconds,
                        "duration_seconds": window.samples.size / window.sample_rate,
                    }
                )
        if not windows:
            raise HTTPException(422, "Nenhuma amostra de audio Opus decodificada.")
        return {
            "chunks_received": len(chunks),
            "bytes_received": total_bytes,
            "sample_rate": SAMPLE_RATE,
            "duration_seconds": end_sample / SAMPLE_RATE,
            "windows": windows,
        }
    except HTTPException:
        raise
    except (av.error.FFmpegError, ValueError, TypeError) as exc:
        raise HTTPException(
            422,
            "WebM/Opus invalido: use uma unica gravacao, com cabecalho inicial "
            "e todos os chunks originais na ordem de captura.",
        ) from exc


@router.post("/incremental-audio", summary="Decodifica WebM/Opus apos upload")
async def decode_incremental_audio(
    request: Request, _current_user: User = Depends(get_current_user)
) -> dict:
    """Autentica antes de ler/spoolar o multipart; preserva a ordem dos chunks."""
    raw_length = request.headers.get("content-length")
    if raw_length is None:
        raise HTTPException(411, "Content-Length obrigatorio para este diagnostico.")
    try:
        if not raw_length.isascii() or not raw_length.isdecimal():
            raise ValueError("Content-Length invalido")
        content_length = int(raw_length)
    except ValueError as exc:
        raise HTTPException(400, "Content-Length invalido.") from exc
    if content_length <= 0:
        raise HTTPException(400, "Corpo multipart vazio.")
    if content_length > MAX_REQUEST_BYTES:
        raise HTTPException(413, "Requisicao excede 16 MiB mais 1 MiB de overhead.")
    content_type = request.headers.get("content-type", "").split(";", 1)[0]
    if content_type.strip().lower() != "multipart/form-data":
        raise HTTPException(415, "Envie multipart/form-data com campos chunks.")

    # Nenhum parametro File/Form: FastAPI resolve a autenticacao sem ler o corpo.
    form = await request.form(max_files=MAX_CHUNKS, max_fields=MAX_CHUNKS)
    try:
        chunks: list[UploadFile] = []
        for name, item in form.multi_items():
            if name != "chunks" or not isinstance(item, UploadFile):
                raise HTTPException(400, "Envie somente arquivos no campo chunks.")
            chunks.append(item)
        # IO dos arquivos e PyAV ficam fora do event loop; nao retorna amostras PCM.
        return await run_in_threadpool(_decode_chunks, chunks)
    finally:
        # Inclui arquivos de campos invalidos e falhas de validacao/decodificacao.
        await form.close()
