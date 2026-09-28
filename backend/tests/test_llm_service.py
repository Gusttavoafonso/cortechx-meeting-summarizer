import pytest
from app.services.llm.base import BaseLLMProvider
from app.services.llm.service import LLMService


class FakeLLMProvider(BaseLLMProvider):
    def generate(self, prompt: str) -> str:
        return f"Resposta: {prompt}"


def test_llm_service_initialization() -> None:
    provider = FakeLLMProvider()

    service = LLMService(provider)

    assert service.provider is provider


def test_llm_service_generate() -> None:
    provider = FakeLLMProvider()
    service = LLMService(provider)

    response = service.generate("Teste")

    assert response == "Resposta: Teste"


def test_llm_service_rejects_empty_prompt() -> None:
    provider = FakeLLMProvider()
    service = LLMService(provider)

    with pytest.raises(ValueError, match="Prompt cannot be empty"):
        service.generate("")


def test_llm_service_rejects_blank_prompt() -> None:
    provider = FakeLLMProvider()
    service = LLMService(provider)

    with pytest.raises(ValueError, match="Prompt cannot be empty"):
        service.generate("   ")