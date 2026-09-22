from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.summary import SummaryResponse
from app.services.llm import OpenAISummaryLLM
from app.services.summarization import create_summarization_service

router = APIRouter(prefix="/summaries", tags=["Summarization"])


class SummarizationRequest(BaseModel):
    """Corpo da requisição para gerar o resumo de uma reunião."""

    transcript: str = Field(..., description="Transcrição bruta da reunião.")


@router.post("", response_model=SummaryResponse)
def summarize_meeting(payload: SummarizationRequest) -> SummaryResponse:
    """Gera um resumo estruturado a partir de uma transcrição."""
    if settings.openai_api_key is None:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY não configurada")
    if not payload.transcript.strip():
        raise HTTPException(status_code=422, detail="A transcrição não pode estar vazia")

    try:
        service = create_summarization_service(
            OpenAISummaryLLM(
                api_key=settings.openai_api_key.get_secret_value(),
                model=settings.openai_model,
            ),
            max_chars=settings.summary_chunk_size,
            overlap_chars=settings.summary_chunk_overlap,
        )
        return service.summarize(payload.transcript)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc