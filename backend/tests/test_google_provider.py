from unittest.mock import MagicMock, patch
import pytest
from google.genai import errors
from app.services.llm.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMProviderError,
    LLMEmptyResponseError,
)
from app.services.llm.providers.gemini_provider import GeminiProvider
from app.services.llm.service import _build_provider


def make_api_error(error_cls, code: int, message: str = "erro simulado"):
    """Monta uma instância de erro do SDK sem precisar de resposta HTTP real."""
    exc = error_cls.__new__(error_cls)
    exc.code = code
    exc.message = message
    return exc


@patch("app.services.llm.providers.gemini_provider.genai.Client")
def test_gemini_provider_generate_success(mock_client_cls):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text="ok")
    mock_client_cls.return_value = mock_client

    provider = GeminiProvider(api_key="fake_key", model="gemini-3.6-flash")
    result = provider.generate("prompt de teste")

    assert result == "ok"


@patch("app.services.llm.providers.gemini_provider.genai.Client")
def test_gemini_provider_empty_response(mock_client_cls):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text=None)
    mock_client_cls.return_value = mock_client

    provider = GeminiProvider(api_key="fake_key", model="gemini-3.6-flash")

    with pytest.raises(LLMEmptyResponseError):
        provider.generate("prompt de teste")


@patch("app.services.llm.providers.gemini_provider.genai.Client")
def test_gemini_provider_authentication_error(mock_client_cls):
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = make_api_error(
        errors.ClientError, code = 401
    )
    mock_client_cls.return_value = mock_client

    provider = GeminiProvider(api_key="fake_key", model="gemini-3.6-flash")

    with pytest.raises(LLMAuthenticationError):
        provider.generate("prompt de teste")


@patch("app.services.llm.providers.gemini_provider.genai.Client")
def test_gemini_provider_client_error_generic(mock_client_cls):
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = make_api_error(
        errors.ClientError, code = 429
    )
    mock_client_cls.return_value = mock_client

    provider = GeminiProvider(api_key="fake_key", model="gemini-3.6-flash")

    with pytest.raises(LLMProviderError):
        provider.generate("prompt de teste")


@patch("app.services.llm.providers.gemini_provider.genai.Client")
def test_gemini_provider_server_error(mock_client_cls):
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = make_api_error(
        errors.ServerError, code = 500
    )
    mock_client_cls.return_value = mock_client

    provider = GeminiProvider(api_key="fake_key", model="gemini-3.6-flash")

    with pytest.raises(LLMProviderError):
        provider.generate("prompt de teste")


def test_build_provider_missing_configuration(monkeypatch):
    monkeypatch.setattr("app.services.llm.service.settings.llm_provider", None)
    monkeypatch.setattr("app.services.llm.service.settings.llm_model", None)
    monkeypatch.setattr("app.services.llm.service.settings.llm_api_key", None)

    with pytest.raises(LLMConfigurationError):
        _build_provider()
