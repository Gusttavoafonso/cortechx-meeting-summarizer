class LLMError(Exception):
    """Erro base pra qualquer falha do serviço."""

class LLMConfigurationError(LLMError):
    """Configuração obrigatória ausente ou inválida(API Key, provider, model)."""

class LLMAuthenticationError(LLMError):
    """Falha de autenticação com o provider. """

class LLMTimeoutError(LLMError):
    """A chamada ao provider excedeu o tempo limite."""

class LLMEmptyResponseError(LLMError):
    """O provider retornou uma resposta vazia ou sem conteúdo utilizável."""

class LLMProviderError(LLMError):
    """Erro genérico não listado."""

