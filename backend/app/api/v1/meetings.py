from collections.abc import Callable

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_session
from app.core.exceptions import (
    LLMError,
    TranscriptionAudioCorruptedError,
)
from app.models.meeting_status import IN_PROGRESS_STATUSES, MeetingStatus
from app.models.user import User
from app.repositories.audio_repository import AudioRepository
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.summary_repository import SummaryRepository
from app.repositories.transcript_repository import (
    InvalidTranscriptSegmentError,
    TranscriptRepository,
)
from app.schemas.audio import AudioUploadResponse
from app.schemas.meeting import (
    GlobalTaskItemResponse,
    MeetingCreate,
    MeetingProcessOptions,
    MeetingProcessResponse,
    MeetingResponse,
    MeetingStatsResponse,
    MeetingStatusResponse,
    MeetingSummaryPreview,
)
from app.schemas.summary import SummaryResponse
from app.schemas.transcription import TranscriptResponse
from app.services.audio_storage import AudioStorageService
from app.services.llm.service import get_llm_service, resolve_user_llm_config
from app.services.meeting_service import MeetingNotFoundError, MeetingService
from app.services.summarization.service import create_summarization_service
from app.services.summary_service import (
    MeetingNotFoundError as SummaryMeetingNotFoundError,
)
from app.services.summary_service import (
    SummaryAlreadyProcessingError,
    SummaryService,
    TranscriptNotFoundError,
)
from app.services.transcription import (
    BaseSpeechToTextService,
    get_speech_to_text_service,
)
from app.workers.meeting_job import enqueue_meeting_processing

router = APIRouter(dependencies=[Depends(get_current_user)])


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


def get_meeting_job_dispatcher() -> Callable[[int, BackgroundTasks | None], None]:
    return enqueue_meeting_processing


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


def get_summary_repository(db: Session = Depends(get_session)) -> SummaryRepository:
    return SummaryRepository(db)


def get_summary_service(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    transcript_repo: TranscriptRepository = Depends(get_transcript_repository),
    summary_repo: SummaryRepository = Depends(get_summary_repository),
) -> SummaryService:
    try:
        user_llm_cfg = resolve_user_llm_config(db, current_user.id)
        if user_llm_cfg is not None:
            llm = get_llm_service(
                provider=user_llm_cfg["provider"],
                model=user_llm_cfg["model"],
                api_key=user_llm_cfg["api_key"],
            )
        else:
            llm = get_llm_service()
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Serviço de LLM não configurado ou indisponível: {exc}",
        ) from exc
    summarization = create_summarization_service(llm)
    return SummaryService(
        summarization=summarization,
        summary_repository=summary_repo,
        meeting_repository=meeting_repo,
        transcript_repository=transcript_repo,
    )


def _mark_failed(
    meeting_id: int, meeting_repo: MeetingRepository, message: str
) -> None:
    """Marca a reunião como falha no banco de dados com uma mensagem de erro."""
    MeetingService(meeting_repo).update_status(
        meeting_id, MeetingStatus.FAILED, error_message=message
    )


def _to_meeting_response(
    meeting, *, include_transcript: bool = True
) -> MeetingResponse:
    summary_preview = None
    if getattr(meeting, "summary", None) is not None:
        summary_preview = MeetingSummaryPreview(
            objective=meeting.summary.objective,
            summary=meeting.summary.summary,
            tasks_count=len(getattr(meeting, "tasks", None) or []),
        )
    transcript = (
        TranscriptResponse.model_validate(meeting.transcript)
        if include_transcript and getattr(meeting, "transcript", None) is not None
        else None
    )
    return MeetingResponse(
        id=meeting.id,
        title=meeting.title,
        status=meeting.status,
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
        processing_started_at=meeting.processing_started_at,
        processing_completed_at=meeting.processing_completed_at,
        last_error=meeting.last_error,
        audio=AudioUploadResponse.model_validate(meeting.audio)
        if getattr(meeting, "audio", None) is not None
        else None,
        transcript=transcript,
        summary=summary_preview,
    )


@router.post(
    "",
    response_model=MeetingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar reunião",
)
def create_meeting(
    meeting_in: MeetingCreate,
    current_user: User = Depends(get_current_user),
    meeting_service: MeetingService = Depends(get_meeting_service),
) -> MeetingResponse:
    meeting = meeting_service.create(meeting_in, user_id=current_user.id)
    return MeetingResponse.model_validate(meeting)


@router.get(
    "",
    response_model=list[MeetingResponse],
    summary="Listar reuniões",
)
def list_meetings(
    current_user: User = Depends(get_current_user),
    meeting_service: MeetingService = Depends(get_meeting_service),
) -> list[MeetingResponse]:
    meetings = meeting_service.list_all(user_id=current_user.id)
    return [_to_meeting_response(m, include_transcript=False) for m in meetings]


@router.get(
    "/stats",
    response_model=MeetingStatsResponse,
    summary="Indicadores agregados das reuniões do usuário",
)
def get_meeting_stats(
    current_user: User = Depends(get_current_user),
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
) -> MeetingStatsResponse:
    stats = meeting_repo.get_stats_by_user(current_user.id)
    return MeetingStatsResponse(
        total_meetings=stats["total_meetings"],
        completed_meetings=stats["completed_meetings"],
        processing_meetings=stats["processing_meetings"],
        failed_meetings=stats["failed_meetings"],
        total_audio_seconds=stats["total_audio_seconds"],
        total_tasks=stats["total_tasks"],
        recent_meetings=[
            _to_meeting_response(m, include_transcript=False)
            for m in stats["recent_meetings"]
        ],
    )


@router.get(
    "/tasks",
    response_model=list[GlobalTaskItemResponse],
    summary="Listar todas as tarefas extraídas das reuniões do usuário",
)
def list_user_tasks(
    current_user: User = Depends(get_current_user),
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
) -> list[GlobalTaskItemResponse]:
    rows = meeting_repo.list_tasks_by_user(current_user.id)
    return [
        GlobalTaskItemResponse(
            id=task.id,
            meeting_id=task.meeting_id,
            meeting_title=meeting_title,
            meeting_status=meeting_status,
            description=task.description,
            responsible=task.responsible,
            deadline=task.deadline,
            created_at=task.created_at,
        )
        for task, meeting_title, meeting_status in rows
    ]


@router.get(
    "/{meeting_id}",
    response_model=MeetingResponse,
    summary="Obter reunião por ID",
)
def get_meeting(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    meeting_service: MeetingService = Depends(get_meeting_service),
) -> MeetingResponse:
    validate_meeting_id(meeting_id)
    try:
        meeting = meeting_service.get_by_id(meeting_id, user_id=current_user.id)
    except MeetingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )
    return _to_meeting_response(meeting, include_transcript=True)


@router.delete(
    "/{meeting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Excluir reunião e seu áudio",
)
def delete_meeting(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    storage_service: AudioStorageService = Depends(get_audio_storage_service),
) -> Response:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id_and_user(meeting_id, current_user.id)
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )
    if meeting.status in IN_PROGRESS_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Não é possível excluir uma reunião enquanto ela está em processamento."
            ),
        )

    audio_path = meeting.audio.file_path if meeting.audio is not None else None
    meeting_repo.delete(meeting)
    if audio_path:
        storage_service.delete_file(audio_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    current_user: User = Depends(get_current_user),
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    audio_repo: AudioRepository = Depends(get_audio_repository),
    transcript_repo: TranscriptRepository = Depends(get_transcript_repository),
    storage_service: AudioStorageService = Depends(get_audio_storage_service),
) -> AudioUploadResponse:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id_and_user(meeting_id, current_user.id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )

    # Impede substituição de áudio durante transcrição ou processamento em andamento
    if meeting.status in (
        "transcribing",
        MeetingStatus.TRANSCRIBING,
        MeetingStatus.PROCESSING,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Não é possível enviar ou substituir o áudio enquanto a reunião "
                "está sendo transcrita ou processada."
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
    duration_seconds = storage_service.extract_audio_duration(
        storage_service.get_file_path(relative_path)
    )

    try:
        audio_record = audio_repo.save_audio_metadata(
            meeting_id=meeting_id,
            original_filename=file.filename or saved_filename,
            filename=saved_filename,
            file_path=relative_path,
            content_type=resolved_content_type,
            file_size_bytes=total_bytes,
            duration_seconds=duration_seconds,
        )

        # Se já existia transcrição para o áudio anterior, invalida/limpa
        transcript_repo.delete_by_meeting_id(meeting_id)

        MeetingService(meeting_repo).update_status(
            meeting_id, MeetingStatus.AUDIO_UPLOADED
        )
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
        duration_seconds=audio_record.duration_seconds,
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
    current_user: User = Depends(get_current_user),
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    audio_repo: AudioRepository = Depends(get_audio_repository),
) -> AudioUploadResponse:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id_and_user(meeting_id, current_user.id)
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
        duration_seconds=audio_record.duration_seconds,
        file_path=audio_record.file_path,
        uploaded_at=audio_record.created_at,
    )


@router.get(
    "/{meeting_id}/audio/file",
    summary="Baixar ou reproduzir o arquivo de áudio da reunião",
)
def download_audio_file(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    audio_repo: AudioRepository = Depends(get_audio_repository),
    storage_service: AudioStorageService = Depends(get_audio_storage_service),
) -> FileResponse:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id_and_user(meeting_id, current_user.id)
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

    file_path = storage_service.get_file_path(audio_record.file_path)
    return FileResponse(
        path=file_path,
        media_type=audio_record.content_type,
        filename=audio_record.original_filename,
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
    current_user: User = Depends(get_current_user),
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    audio_repo: AudioRepository = Depends(get_audio_repository),
    transcript_repo: TranscriptRepository = Depends(get_transcript_repository),
    storage_service: AudioStorageService = Depends(get_audio_storage_service),
    stt_service: BaseSpeechToTextService = Depends(get_transcription_service),
) -> TranscriptResponse:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id_and_user(meeting_id, current_user.id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )

    # Impede execuções concorrentes na mesma reunião
    if meeting.status in (
        "transcribing",
        MeetingStatus.TRANSCRIBING,
        MeetingStatus.PROCESSING,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A reunião já está em processo de transcrição ou processamento.",
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
    MeetingService(meeting_repo).update_status(meeting_id, MeetingStatus.TRANSCRIBING)

    # Executa transcrição com tratamento de falha no provedor de STT
    try:
        result = stt_service.transcribe(audio_file_path, language="pt")
    except (OSError, IOError) as io_err:
        _mark_failed(meeting_id, meeting_repo, f"Erro de leitura do áudio: {io_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro inesperado durante a leitura do arquivo de áudio: {io_err}",
        )
    except TranscriptionAudioCorruptedError as corr_err:
        _mark_failed(
            meeting_id,
            meeting_repo,
            f"Arquivo de áudio corrompido ou formato ilegível: {corr_err}",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Arquivo de áudio corrompido ou formato ilegível: {corr_err}",
        )
    except Exception as stt_err:
        _mark_failed(
            meeting_id,
            meeting_repo,
            f"Falha no serviço de Speech-to-Text: {stt_err}",
        )
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
        _mark_failed(
            meeting_id,
            meeting_repo,
            "O serviço de transcrição retornou uma resposta vazia. "
            "Áudio mudo ou inaudível.",
        )
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
        MeetingService(meeting_repo).update_status(
            meeting_id, MeetingStatus.TRANSCRIBED
        )
        db.commit()
    except InvalidTranscriptSegmentError as exc:
        db.rollback()
        _mark_failed(meeting_id, meeting_repo, str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        _mark_failed(meeting_id, meeting_repo, "Falha ao persistir a transcrição.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao persistir a transcrição.",
        ) from exc

    db.refresh(transcript)
    return TranscriptResponse.model_validate(transcript)


# rota para obter a transcrição completa da reunião, incluindo segmentos
@router.get(
    "/{meeting_id}/transcript",
    response_model=TranscriptResponse,
    summary="Obter transcrição da reunião",
)
def get_meeting_transcript(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    transcript_repo: TranscriptRepository = Depends(get_transcript_repository),
) -> TranscriptResponse:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id_and_user(meeting_id, current_user.id)

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


@router.post(
    "/{meeting_id}/process",
    response_model=MeetingProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Iniciar processamento assíncrono da reunião",
    description=(
        "Valida a reunião e seu áudio, reserva o estado PROCESSING para impedir "
        "execuções duplicadas simultâneas e dispara o pipeline em background."
    ),
)
def process_meeting_async(
    meeting_id: int,
    background_tasks: BackgroundTasks,
    options: MeetingProcessOptions | None = Body(default=None),
    current_user: User = Depends(get_current_user),
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    audio_repo: AudioRepository = Depends(get_audio_repository),
    storage_service: AudioStorageService = Depends(get_audio_storage_service),
    job_dispatcher: Callable[..., None] = Depends(
        get_meeting_job_dispatcher
    ),
) -> MeetingProcessResponse:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id_and_user(meeting_id, current_user.id)

    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )

    if meeting.status in (MeetingStatus.PROCESSING, MeetingStatus.TRANSCRIBING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A reunião com ID {meeting_id} já está em processamento.",
        )

    audio_record = audio_repo.get_by_meeting_id(meeting_id)
    if not audio_record or not storage_service.file_exists(audio_record.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Arquivo de áudio não encontrado para a reunião com ID {meeting_id}."
            ),
        )

    previous_status = meeting.status
    if not meeting_repo.try_claim_processing(meeting_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A reunião com ID {meeting_id} já está em processamento.",
        )

    options_dict = options.model_dump(exclude_none=True) if options else None
    meeting.processing_options = options_dict
    meeting_repo.db.add(meeting)
    meeting_repo.db.commit()

    try:
        if options_dict:
            job_dispatcher(meeting_id, background_tasks, options=options_dict)
        else:
            job_dispatcher(meeting_id, background_tasks)
    except Exception as exc:
        MeetingService(meeting_repo).update_status(meeting_id, previous_status)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Não foi possível enfileirar o processamento da reunião: {exc}",
        ) from exc

    return MeetingProcessResponse(
        meeting_id=meeting_id,
        status=MeetingStatus.PROCESSING,
    )


@router.post(
    "/{meeting_id}/summary",
    response_model=SummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Gerar resumo da reunião",
    description=(
        "Execute o pipeline de sumarização(chunking + llm) sobre a "
        "transcrição já existente e persiste o resultado. Reprocessa e "
        "substitui o resumo caso já exista um."
    ),
)
def create_summary(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    summary_service: SummaryService = Depends(get_summary_service),
) -> SummaryResponse:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id_and_user(meeting_id, current_user.id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )
    try:
        return summary_service.generate_and_persist(meeting_id)
    except SummaryMeetingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )
    except TranscriptNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A reunião com ID {meeting_id} ainda não possui transcrição "
                "disponível para sumarização."
            ),
        )
    except SummaryAlreadyProcessingError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A reunião com ID {meeting_id} já está sendo processada.",
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao gerar resumo da reunião: {exc}",
        ) from exc


@router.get(
    "/{meeting_id}/summary",
    response_model=SummaryResponse,
    summary="Obter resumo da reunião",
)
def get_summary(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    summary_repo: SummaryRepository = Depends(get_summary_repository),
) -> SummaryResponse:
    validate_meeting_id(meeting_id)

    meeting = meeting_repo.get_by_id_and_user(meeting_id, current_user.id)
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )

    summary = summary_repo.get_by_meeting_id(meeting_id)
    if summary is not None:
        return SummaryResponse.model_validate(summary)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Resumo ainda não gerado pra reunião com ID {meeting_id}.",
    )


@router.post(
    "/{meeting_id}/retry",
    response_model=MeetingResponse,
    status_code=status.HTTP_200_OK,
    summary="Reprocessar manualmente reunião com falha (retry)",
    description=(
        "Permite o reprocessamento manual de uma reunião cujo status seja FAILED.\n\n"
        "### Regras e Bloqueios:\n"
        "- **404 Not Found:** Reunião não encontrada.\n"
        "- **422 Unprocessable Content:** Áudio ausente no banco ou no disco.\n"
        "- **409 Conflict:** Reunião já em processamento "
        "(`processing` ou `transcribing`).\n"
        "- **409 Conflict:** Reunião já concluída com sucesso (`completed`).\n"
        "- **409 Conflict:** Reunião em estado que não seja falha (`failed`)."
    ),
)
def retry_meeting(
    meeting_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    meeting_repo: MeetingRepository = Depends(get_meeting_repository),
    audio_repo: AudioRepository = Depends(get_audio_repository),
    storage_service: AudioStorageService = Depends(get_audio_storage_service),
) -> MeetingResponse:
    validate_meeting_id(meeting_id)
    meeting = meeting_repo.get_by_id_and_user(meeting_id, current_user.id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )

    audio_record = audio_repo.get_by_meeting_id(meeting_id)
    if not audio_record or not storage_service.file_exists(audio_record.file_path):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Arquivo de áudio não encontrado para a reunião com ID {meeting_id}."
            ),
        )

    current_status = (
        meeting.status.value
        if hasattr(meeting.status, "value")
        else str(meeting.status).lower()
    )
    if current_status in (
        MeetingStatus.PROCESSING.value,
        MeetingStatus.TRANSCRIBING.value,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A reunião já está em processamento.",
        )

    if current_status == MeetingStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A reunião já foi processada com sucesso.",
        )

    if current_status != MeetingStatus.FAILED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "O endpoint de retry manual é destinado exclusivamente a reuniões "
                f"com falha (FAILED). Status atual: {meeting.status}."
            ),
        )

    MeetingService(meeting_repo).update_status(meeting_id, MeetingStatus.PROCESSING)
    if meeting.processing_options:
        enqueue_meeting_processing(
            meeting_id, background_tasks, options=meeting.processing_options
        )
    else:
        enqueue_meeting_processing(meeting_id, background_tasks)
    return MeetingResponse.model_validate(meeting)


@router.get(
    "/{meeting_id}/status",
    response_model=MeetingStatusResponse,
    summary="Consultar status da reunião",
)
def get_meeting_status(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    meeting_service: MeetingService = Depends(get_meeting_service),
) -> MeetingStatusResponse:
    validate_meeting_id(meeting_id)
    try:
        meeting = meeting_service.get_by_id(meeting_id, user_id=current_user.id)
    except MeetingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com id {meeting_id} não encontrada.",
        )
    return MeetingStatusResponse(
        meeting_id=meeting.id,
        status=meeting.status,
        updated_at=meeting.updated_at,
        last_error=meeting.last_error,
    )
