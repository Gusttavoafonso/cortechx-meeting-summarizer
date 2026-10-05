from google import genai
from google.genai import errors

from app.services.llm.base import BaseLLMProvider
from app.services.llm.exceptions import (
    LLMAuthenticationError,
    LLMEmptyResponseError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate(self, prompt: str) -> str:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
            )
        except errors.ClientError as exc:
            if exc.code in (401, 403):
                raise LLMAuthenticationError(str(exc)) from exc
            if exc.code == 429:
                raise LLMRateLimitError(str(exc)) from exc
            raise LLMProviderError(str(exc), is_retryable=False) from exc
        except errors.ServerError as exc:
            raise LLMProviderError(str(exc), is_retryable=True) from exc
        except Exception as exc:
            err_msg = str(exc).lower()
            if "timeout" in err_msg or "timed out" in err_msg:
                raise LLMTimeoutError(f"Timeout na chamada ao Gemini: {exc}") from exc
            raise LLMProviderError(str(exc)) from exc

        text = getattr(response, "text", None)
        if not text:
            raise LLMEmptyResponseError("O provider retornou uma resposta vazia.")

        return text
