from app.services.llm.base import BaseLLMProvider
from app.core.config import settings
from app.services.llm.exceptions import LLMConfigurationError
from app.services.llm.providers.gemini_provider import GeminiProvider

class LLMService:
    """Serviço central utilizado pela aplicação para comunicação com LLMs."""

    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider

    def generate(self, prompt: str) -> str:
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        return self.provider.generate(prompt)

def _build_provider() -> BaseLLMProvider:
    try:
        settings.validate_llm_configuration()
    except ValueError as exc:
        raise LLMConfigurationError(str(exc)) from exc

    if settings.llm_provider == "gemini":
        return GeminiProvider(
            api_key = settings.llm_api_key.get_secret_value(),
            model = settings.llm_model,
        )

    raise LLMConfigurationError(f"Provider não suportado: {settings.llm_provider}")

def get_llm_service() -> LLMService:
    return LLMService(_build_provider())