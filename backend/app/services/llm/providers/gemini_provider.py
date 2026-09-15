from google import genai
from google.genai import errors

from app.services.llm.base import BaseLLMProvider
from app.services.llm.exceptions import (
    LLMAuthenticationError,
    LLMEmptyResponseError,
    LLMProviderError,
)

class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate(self,  prompt: str) -> str:
        try:
            response = self._client.models.generate_content(
                model = self._model,
                contents=prompt,
            )
        except errors.ClientError as exc:
            if exc.code == 401 or exc.code == 403:
                raise LLMAuthenticationError(str(exc)) from exc
            raise LLMProviderError(str(exc)) from exc
        except errors.ServerError as exc:
            raise LLMProviderError(str(exc)) from exc
        
        text = getattr(response, "text", None)
        if not text:
            raise LLMEmptyResponseError("O provider retornou uma resposta vazia.")

        return text