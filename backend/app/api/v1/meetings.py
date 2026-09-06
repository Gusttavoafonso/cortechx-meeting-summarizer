from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_session
from app.repositories.audio_repository import AudioRepository
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.schemas.audio import AudioUploadResponse
from app.schemas.meeting import MeetingCreate, MeetingResponse
from app.schemas.transcription import TranscriptResponse
from app.services.audio_storage import AudioStorageService
from app.services.transcription import (
    BaseSpeechToTextService,
    get_speech_to_text_service,
)

router = APIRouter()


def get_meeting_repository(db: Session = Depends(get_session)) -> MeetingRepository:
    return MeetingRepository(db)


def get_audio_repository(db: Session = Depends(get_session)) -> AudioRepository:
    return AudioRepository(db)


def get_transcript_repository(
    db: Session = Depends(get_session),
) -> TranscriptRepository:
    return TranscriptRepository(db)


def get_audio_storage_service() -> AudioStorageService:
    return AudioStorageService()


def get_transcription_service() -> BaseSpeechToTextService:
    return get_speech_to_text_service()


def validate_meeting_id(meeting_id: int) -> int:
    if meeting_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Identificador de reunião inválido. O ID deve ser um "
                "número inteiro positivo."
            ),
        )
    return meeting_id


@router.post(
    "",
    response_model=MeetingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar reunião",
)
def create_meeting(
    meeting_in: MeetingCreate,
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
) -> MeetingResponse:
    meeting = meeting_repo.create(title=meeting_in.title)
    return MeetingResponse.model_validate(meeting)


@router.get(
    "/{meeting_id}",
    response_model=MeetingResponse,
    summary="Obter reunião por ID",
)
def get_meeting(
    meeting_id: int,
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
) -> MeetingResponse:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id(meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )
    return MeetingResponse.model_validate(meeting)


@router.post(
    "/{meeting_id}/audio",
    response_model=AudioUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de áudio da reunião",
    description=(
        "Recebe uma gravação de áudio ou vídeo compatível associada a uma "
        "reunião existente.\n\n"
        "### Regras de Validação:\n"
        "- **Formatos aceitos:** "
        f"{', '.join(sorted(settings.ALLOWED_AUDIO_EXTENSIONS))}.\n"
        "- **MIME types permitidos:** `audio/mpeg`, `audio/wav`, `audio/mp4`, "
        "`audio/webm`, `video/mp4`, etc.\n"
        f"- **Tamanho máximo:** {settings.MAX_AUDIO_SIZE_MB} MB "
        "(rejeita com HTTP 413 se exceder).\n"
        "- **Arquivo vazio:** Arquivos com 0 bytes são rejeitados (HTTP 400).\n"
        "- **Reunião:** O identificador deve ser um inteiro positivo e existir no "
        "banco (HTTP 400 / 404)."
    ),
)
def upload_audio(
    meeting_id: int,
    file: UploadFile = File(...),
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    audio_repo: AudioRepository = Depends(get_audio_repository),
    storage_service: AudioStorageService = Depends(get_audio_storage_service),
) -> AudioUploadResponse:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id(meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )

    # Remove áudio anterior do disco caso já exista para evitar arquivos órfãos
    existing_audio = audio_repo.get_by_meeting_id(meeting_id)
    if existing_audio and existing_audio.file_path:
        storage_service.delete_file(existing_audio.file_path)

    saved_filename, relative_path, total_bytes = storage_service.save_audio_file(
        meeting_id=meeting_id,
        file=file,
    )

    audio_record = audio_repo.save_audio_metadata(
        meeting_id=meeting_id,
        original_filename=file.filename or saved_filename,
        filename=saved_filename,
        file_path=relative_path,
        content_type=file.content_type or "audio/mpeg",
        file_size_bytes=total_bytes,
    )

    meeting_repo.update_status(meeting, status="audio_uploaded")

    return AudioUploadResponse(
        meeting_id=meeting_id,
        filename=audio_record.filename,
        original_filename=audio_record.original_filename,
        content_type=audio_record.content_type,
        file_size_bytes=audio_record.file_size_bytes,
        file_path=audio_record.file_path,
        uploaded_at=audio_record.created_at,
    )


@router.get(
    "/{meeting_id}/audio",
    response_model=AudioUploadResponse,
    summary="Obter metadados do áudio da reunião",
)
def get_audio_metadata(
    meeting_id: int,
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    audio_repo: AudioRepository = Depends(get_audio_repository),
) -> AudioUploadResponse:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id(meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )

    audio_record = audio_repo.get_by_meeting_id(meeting_id)
    if not audio_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Áudio não encontrado para a reunião com ID {meeting_id}.",
        )

    return AudioUploadResponse(
        meeting_id=meeting_id,
        filename=audio_record.filename,
        original_filename=audio_record.original_filename,
        content_type=audio_record.content_type,
        file_size_bytes=audio_record.file_size_bytes,
        file_path=audio_record.file_path,
        uploaded_at=audio_record.created_at,
    )


@router.post(
    "/{meeting_id}/transcribe",
    response_model=TranscriptResponse,
    status_code=status.HTTP_200_OK,
    summary="Executar transcrição do áudio da reunião",
    description=(
        "Inicia o pipeline de transcrição do áudio associado à reunião via "
        "Speech-to-Text (local via faster-whisper com Silero VAD ou Groq via nuvem)."
    ),
)
def transcribe_meeting(
    meeting_id: int,
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    audio_repo: AudioRepository = Depends(get_audio_repository),
    transcript_repo: TranscriptRepository = Depends(get_transcript_repository),
    storage_service: AudioStorageService = Depends(get_audio_storage_service),
    stt_service: BaseSpeechToTextService = Depends(get_transcription_service),
) -> TranscriptResponse:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id(meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )

    audio_record = audio_repo.get_by_meeting_id(meeting_id)
    if not audio_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Reunião com ID {meeting_id} não possui áudio associado "
                "para transcrição."
            ),
        )

    if not storage_service.file_exists(audio_record.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo de áudio não encontrado no armazenamento.",
        )

    audio_file_path = storage_service.get_file_path(audio_record.file_path)

    # Atualiza status para transcrevendo
    meeting_repo.update_status(meeting, status="transcribing")

    # Executa transcrição
    result = stt_service.transcribe(audio_file_path, language="pt")

    # Persiste transcrição e segmentos
    transcript = transcript_repo.save_transcript(
        meeting_id=meeting_id,
        content=result.text,
        segments=result.segments,
    )

    # Atualiza status para transcrito
    meeting_repo.update_status(meeting, status="transcribed")

    return TranscriptResponse.model_validate(transcript)


@router.get(
    "/{meeting_id}/transcript",
    response_model=TranscriptResponse,
    summary="Obter transcrição da reunião",
)
def get_meeting_transcript(
    meeting_id: int,
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    transcript_repo: TranscriptRepository = Depends(get_transcript_repository),
) -> TranscriptResponse:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id(meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )

    transcript = transcript_repo.get_by_meeting_id(meeting_id)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcrição não encontrada para a reunião com ID {meeting_id}.",
        )

    return TranscriptResponse.model_validate(transcript)
