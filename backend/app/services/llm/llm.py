"""Abstração e implementação do cliente de LLM usado na sumarização."""

from typing import Protocol

from app.schemas.summary import SummaryResponse

class LLMService(Protocol):
    def summarize(self, prompt: str) -> SummaryResponse:
        """Executa o prompt e retorna uma resposta estruturada."""


class OpenAISummaryLLM:
    """Cliente OpenAI com Structured Outputs via Pydantic."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY não configurada")
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def summarize(self, prompt: str) -> SummaryResponse:
        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "Você é um assistente de sumarização fiel de reuniões.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format=SummaryResponse,
        )

        message = response.choices[0].message
        if getattr(message, "refusal", None):
            raise ValueError(f"LLM recusou a solicitação: {message.refusal}")
        if message.parsed is None:
            raise ValueError("LLM não retornou uma saída estruturada válida")
        return message.parsed