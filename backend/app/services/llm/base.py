from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Contrato que todos os providers de LLM devem implementar."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Envia um prompt ao modelo e retorna o conteúdo gerado."""
        raise NotImplementedError