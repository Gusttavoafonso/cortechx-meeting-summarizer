from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_session
from app.repositories.audio_repository import AudioRepository
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.transcript_repository import (
    InvalidTranscriptSegmentError,
    TranscriptRepository,
)
from app.schemas.audio import AudioUploadResponse
from app.schemas.meeting import MeetingCreate, MeetingResponse
from app.schemas.transcription import TranscriptResponse
from app.services.audio_storage import AudioStorageService
from app.services.diarization import (
    DiarizationAssociationError,
    DiarizationError,
    DiarizationService,
    PyannoteDiarizationProvider,
)
from app.services.meeting_service import MeetingNotFoundError, MeetingService
from app.services.transcription import (
    BaseSpeechToTextService,
    get_speech_to_text_service,
)

router = APIRouter()


def get_meeting_repository(db: Session = Depends(get_session)) -> MeetingRepository:
    return MeetingRepository(db)


def get_meeting_service(
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
) -> MeetingService:
    return MeetingService(meeting_repo)


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


def get_diarization_service() -> DiarizationService:
    return DiarizationService(PyannoteDiarizationProvider())


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
    meeting_service: MeetingService = Depends(get_meeting_service),
) -> MeetingResponse:
    meeting = meeting_service.create(meeting_in)
    return MeetingResponse.model_validate(meeting)


@router.get(
    "",
    response_model=list[MeetingResponse],
    summary="Listar reuniões",
)
def list_meetings(
    meeting_service: MeetingService = Depends(get_meeting_service),
) -> list[MeetingResponse]:
    meetings = meeting_service.list_all()
    return [MeetingResponse.model_validate(m) for m in meetings]


@router.get(
    "/{meeting_id}",
    response_model=MeetingResponse,
    summary="Obter reunião por ID",
)
def get_meeting(
    meeting_id: int,
    meeting_service: MeetingService = Depends(get_meeting_service),
) -> MeetingResponse:
    validate_meeting_id(meeting_id)
    try:
        meeting = meeting_service.get_by_id(meeting_id)
    except MeetingNotFoundError:
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
    transcript_repo: TranscriptRepository = Depends(get_transcript_repository),
    storage_service: AudioStorageService = Depends(get_audio_storage_service),
) -> AudioUploadResponse:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id(meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )

    # Impede substituição de áudio durante transcrição em andamento
    if meeting.status == "transcribing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Não é possível enviar ou substituir o áudio enquanto a reunião "
                "está sendo transcrita."
            ),
        )

    existing_audio = audio_repo.get_by_meeting_id(meeting_id)
    old_file_path = existing_audio.file_path if existing_audio else None

    # Salva o novo arquivo PRIMEIRO antes de remover o anterior
    saved_filename, relative_path, total_bytes, resolved_content_type = (
        storage_service.save_audio_file(
            meeting_id=meeting_id,
            file=file,
        )
    )

    try:
        audio_record = audio_repo.save_audio_metadata(
            meeting_id=meeting_id,
            original_filename=file.filename or saved_filename,
            filename=saved_filename,
            file_path=relative_path,
            content_type=resolved_content_type,
            file_size_bytes=total_bytes,
        )

        # Se já existia transcrição para o áudio anterior, invalida/limpa
        transcript_repo.delete_by_meeting_id(meeting_id)

        meeting_repo.update_status(meeting, status="audio_uploaded")
    except Exception as db_exc:
        # Se a persistência falhar, remove o arquivo gravado para evitar arquivo órfão
        storage_service.delete_file(relative_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao registrar metadados do áudio no banco de dados: {db_exc}",
        )

    # Exclui o arquivo antigo do disco agora que o novo arquivo
    # e registro foram comitados com sucesso
    if old_file_path and old_file_path != relative_path:
        storage_service.delete_file(old_file_path)

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
    db: Session = Depends(get_session),
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

    # Impede execuções concorrentes na mesma reunião
    if meeting.status == "transcribing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A reunião já está em processo de transcrição.",
        )

    audio_record = audio_repo.get_by_meeting_id(meeting_id)
    if not audio_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Arquivo de áudio não encontrado para a reunião com ID {meeting_id}."
            ),
        )

    if not storage_service.file_exists(audio_record.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo de áudio não encontrado no armazenamento.",
        )

    audio_file_path = storage_service.get_file_path(audio_record.file_path)

    # Tratamento de erro inesperado durante leitura do arquivo
    try:
        with open(audio_file_path, "rb") as f:
            f.read(1024)
    except OSError as io_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(f"Erro inesperado durante a leitura do arquivo de áudio: {io_err}"),
        )

    # Atualiza status para transcrevendo
    meeting_repo.update_status(meeting, status="transcribing")

    # Executa transcrição com tratamento de falha no provedor de STT
    try:
        result = stt_service.transcribe(audio_file_path, language="pt")
    except (OSError, IOError) as io_err:
        meeting_repo.update_status(meeting, status="audio_uploaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro inesperado durante a leitura do arquivo de áudio: {io_err}",
        )
    except Exception as stt_err:
        meeting_repo.update_status(meeting, status="audio_uploaded")
        err_msg = str(stt_err).lower()
        if any(
            token in err_msg
            for token in (
                "invalid data",
                "corrupt",
                "could not find codec",
                "invaliddataerror",
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Arquivo de áudio corrompido ou formato ilegível: {stt_err}",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha no serviço de Speech-to-Text: {stt_err}",
        )

    # Tratamento de resposta vazia do STT (áudio mudo ou inaudível)
    if not result.text or not result.text.strip():
        meeting_repo.update_status(meeting, status="audio_uploaded")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "O serviço de transcrição retornou uma resposta vazia. "
                "O áudio pode conter apenas silêncio ou ser inaudível."
            ),
        )

    # Persiste transcrição, segmentos e status final em uma única transação.
    try:
        transcript = transcript_repo.save_transcript(
            meeting_id=meeting_id,
            content=result.text,
            segments=result.segments,
            commit=False,
        )
        meeting_repo.update_status(meeting, status="transcribed", commit=False)
        db.commit()
    except InvalidTranscriptSegmentError as exc:
        db.rollback()
        meeting_repo.update_status(meeting, status="audio_uploaded")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        meeting_repo.update_status(meeting, status="audio_uploaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao persistir a transcrição.",
        ) from exc

    db.refresh(transcript)
    return TranscriptResponse.model_validate(transcript)


# Rota de diarização do áudio da reunião.
@router.post(
    "/{meeting_id}/diarize",
    response_model=TranscriptResponse,
    status_code=status.HTTP_200_OK,
    summary="Identificar locutores na transcrição da reunião",
    description=(
        "Executa a diarização do áudio da reunião e associa os locutores aos "
        "segmentos já transcritos."
    ),
)
def diarize_meeting(
    meeting_id: int,
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    audio_repo: AudioRepository = Depends(get_audio_repository),
    transcript_repo: TranscriptRepository = Depends(get_transcript_repository),
    storage_service: AudioStorageService = Depends(get_audio_storage_service),
    diarization_service: DiarizationService = Depends(get_diarization_service),
) -> TranscriptResponse:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id(meeting_id)

    # trata erros de reunião inexistente, áudio ausente ou transcrição não realizada
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )

    audio_record = audio_repo.get_by_meeting_id(meeting_id)
    if not audio_record or not storage_service.file_exists(audio_record.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Arquivo de áudio não encontrado para a reunião com ID {meeting_id}."
            ),
        )

    transcript = transcript_repo.get_by_meeting_id(meeting_id)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A reunião precisa ser transcrita antes da diarização.",
        )

    # trata erros de audio ausente no armazenamento ou falha no serviço de diarização
    audio_file_path = storage_service.get_file_path(audio_record.file_path)
    try:
        diarization_segments = diarization_service.diarize(audio_file_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo de áudio não encontrado no armazenamento.",
        ) from None
    except DiarizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha no serviço de diarização: {exc}",
        ) from exc

    try:
        updated_transcript = transcript_repo.apply_diarization(
            transcript,
            diarization_segments,
        )
    except DiarizationAssociationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao persistir a diarização.",
        ) from exc

    # retorna a transcrição atualizada com locutores associados aos segmentos
    return TranscriptResponse.model_validate(updated_transcript)


# rota para obter a transcrição completa da reunião, incluindo segmentos e locutores
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

    # trata erros de reunião inexistente ou transcrição não realizada
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
