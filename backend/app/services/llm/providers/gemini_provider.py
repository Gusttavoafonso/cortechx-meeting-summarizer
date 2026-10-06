from google import genai
from google.genai import errors

from app.core.retry import RetryPolicy
from app.services.llm.base import BaseLLMProvider
from app.services.llm.exceptions import (
    LLMAuthenticationError,
    LLMEmptyResponseError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)


class GeminiProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        retry_policy: RetryPolicy | None = None,
    ):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self.retry_policy = retry_policy or RetryPolicy.from_settings()

    def generate(self, prompt: str) -> str:
        return self.retry_policy.execute(self._generate_attempt, prompt)

    def _generate_attempt(self, prompt: str) -> str:
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
