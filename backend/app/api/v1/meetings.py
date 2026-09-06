from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.repositories.audio_repository import AudioRepository
from app.repositories.meeting_repository import MeetingRepository
from app.schemas.audio import AudioUploadResponse
from app.schemas.meeting import MeetingCreate, MeetingResponse
from app.services.audio_storage import AudioStorageService

router = APIRouter()


def get_meeting_repository(db: Session = Depends(get_session)) -> MeetingRepository:
    return MeetingRepository(db)


def get_audio_repository(db: Session = Depends(get_session)) -> AudioRepository:
    return AudioRepository(db)


def get_audio_storage_service() -> AudioStorageService:
    return AudioStorageService()


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
)
def upload_audio(
    meeting_id: int,
    file: UploadFile = File(...),
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    audio_repo: AudioRepository = Depends(get_audio_repository),
    storage_service: AudioStorageService = Depends(get_audio_storage_service),
) -> AudioUploadResponse:
    meeting = meeting_repo.get_by_id(meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )

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
