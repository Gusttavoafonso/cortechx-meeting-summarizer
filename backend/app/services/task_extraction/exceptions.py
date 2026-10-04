class TaskExtractionError(Exception):
    """Exceção base para erros durante o processo de extração de tarefas."""


class TaskExtractionInvalidResponseError(TaskExtractionError):
    """Lançada quando a resposta do LLM é inválida ou incompatível com o schema."""


class TaskExtractionLLMFailureError(TaskExtractionError):
    """Lançada quando ocorre uma falha na chamada ao serviço de LLM."""
