"""Exceções do serviço de extração de tarefas baseadas no domínio central."""

from app.core.exceptions import (
    ProcessingError,
    TaskExtractionError,
    TaskExtractionInvalidResponseError,
    TaskExtractionLLMFailureError,
)

__all__ = [
    "ProcessingError",
    "TaskExtractionError",
    "TaskExtractionInvalidResponseError",
    "TaskExtractionLLMFailureError",
]
