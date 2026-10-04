"""Templates de prompt usados pelos serviços de IA."""

from app.prompts.summarization import build_summarization_prompt
from app.prompts.task_extraction import (
    TASK_EXTRACTION_PROMPT,
    build_task_extraction_prompt,
)

__all__ = [
    "build_summarization_prompt",
    "TASK_EXTRACTION_PROMPT",
    "build_task_extraction_prompt",
]
