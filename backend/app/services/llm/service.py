from app.services.llm.base import BaseLLMProvider


class LLMService:
    """Serviço central utilizado pela aplicação para comunicação com LLMs."""

    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider

    def generate(self, prompt: str) -> str:
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        return self.provider.generate(prompt)