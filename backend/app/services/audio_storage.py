import re
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import BACKEND_DIR, settings


class BaseAudioStorage(ABC):
    @abstractmethod
    def save_audio_file(
        self, meeting_id: int, file: UploadFile
    ) -> tuple[str, str, int, str]:
        """Salva o arquivo de áudio e retorna metadados do arquivo gravado."""
        pass

    @abstractmethod
    def get_file_path(self, relative_path: str) -> Path:
        """Resolve e retorna o caminho absoluto do arquivo para o pipeline."""
        pass

    @abstractmethod
    def file_exists(self, relative_path: str) -> bool:
        """Verifica se o arquivo existe no armazenamento."""
        pass

    @abstractmethod
    def delete_file(self, relative_path: str) -> bool:
        """Exclui o arquivo do armazenamento se existir."""
        pass


class AudioStorageService(BaseAudioStorage):
    CHUNK_SIZE = 64 * 1024  # 64 KB

    def __init__(
        self, base_storage_path: Path | None = None, max_size_mb: int | None = None
    ) -> None:
        raw_path = base_storage_path or settings.AUDIO_STORAGE_PATH
        self.base_storage_path = (
            raw_path if raw_path.is_absolute() else (BACKEND_DIR / raw_path)
        ).resolve()
        self.max_size_mb = (
            max_size_mb if max_size_mb is not None else settings.MAX_AUDIO_SIZE_MB
        )
        self.max_bytes = self.max_size_mb * 1024 * 1024

    def sanitize_filename(self, filename: str) -> str:
        name = Path(filename).name
        sanitized = re.sub(r"[^\w\-.]", "_", name)
        sanitized = sanitized or "audio"
        stem = Path(sanitized).stem[:180]
        suffix = Path(sanitized).suffix
        return f"{stem}{suffix}" if stem else sanitized

    def validate_file_metadata(self, file: UploadFile) -> tuple[str, str]:
        if not file.filename or not file.filename.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nome de arquivo não informado ou inválido.",
            )

        name = Path(file.filename).name.strip()
        if not name or name in (".", ".."):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nome de arquivo não informado ou inválido.",
            )

        ext = Path(name).suffix.lower()
        if not ext:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O arquivo de áudio enviado não possui extensão.",
            )

        if ext not in settings.ALLOWED_AUDIO_EXTENSIONS:
            allowed = ", ".join(sorted(settings.ALLOWED_AUDIO_EXTENSIONS))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Formato de arquivo '{ext}' não suportado. "
                    f"Extensões permitidas: {allowed}."
                ),
            )

        content_type = (file.content_type or "").lower().strip()
        if not content_type:
            inferred_types = {
                ".mp3": "audio/mpeg",
                ".wav": "audio/wav",
                ".m4a": "audio/mp4",
                ".mp4": "video/mp4",
                ".webm": "audio/webm",
            }
            content_type = inferred_types.get(ext, "")

        if content_type not in settings.ALLOWED_AUDIO_MIME_TYPES:
            allowed_mimes = ", ".join(sorted(settings.ALLOWED_AUDIO_MIME_TYPES))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"MIME type '{content_type}' inválido. "
                    f"Tipos permitidos: {allowed_mimes}."
                ),
            )

        # Verificação antecipada de tamanho se o client já enviou no header
        if file.size is not None:
            if file.size == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="O arquivo de áudio enviado está vazio (0 bytes).",
                )
            if file.size > self.max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=(
                        "Tamanho do arquivo excede o limite máximo "
                        f"permitido de {self.max_size_mb} MB."
                    ),
                )

        return ext, content_type

    def get_file_path(self, relative_path: str) -> Path:
        path = Path(relative_path)
        if path.is_absolute():
            return path
        return BACKEND_DIR / relative_path

    def file_exists(self, relative_path: str) -> bool:
        return self.get_file_path(relative_path).is_file()

    def delete_file(self, relative_path: str) -> bool:
        path = self.get_file_path(relative_path)
        if path.is_file():
            path.unlink()
            return True
        return False

    def save_audio_file(
        self, meeting_id: int, file: UploadFile
    ) -> tuple[str, str, int, str]:
        ext, resolved_content_type = self.validate_file_metadata(file)

        meeting_dir = self.base_storage_path / str(meeting_id)
        meeting_dir.mkdir(parents=True, exist_ok=True)

        clean_name = self.sanitize_filename(file.filename)
        unique_prefix = uuid.uuid4().hex[:8]
        saved_filename = f"{unique_prefix}_{clean_name}"
        destination_path = meeting_dir / saved_filename

        total_bytes = 0

        try:
            with open(destination_path, "wb") as buffer:
                while chunk := file.file.read(self.CHUNK_SIZE):
                    total_bytes += len(chunk)

                    if total_bytes > self.max_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail=(
                                "Tamanho do arquivo excede o limite máximo "
                                f"permitido de {self.max_size_mb} MB."
                            ),
                        )

                    buffer.write(chunk)

            if total_bytes == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="O arquivo de áudio enviado está vazio (0 bytes).",
                )

        except HTTPException:
            if destination_path.exists():
                destination_path.unlink()
            raise
        except OSError as os_err:
            if destination_path.exists():
                destination_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Erro inesperado durante a leitura ou gravação do "
                    f"arquivo de áudio: {os_err}"
                ),
            )
        except Exception as exc:
            if destination_path.exists():
                destination_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Erro inesperado durante o processamento do "
                    f"arquivo de áudio: {exc}"
                ),
            )
        finally:
            file.file.close()

        relative_path = (
            str(destination_path.relative_to(BACKEND_DIR))
            if destination_path.is_relative_to(BACKEND_DIR)
            else str(destination_path)
        )

        return saved_filename, relative_path, total_bytes, resolved_content_type
