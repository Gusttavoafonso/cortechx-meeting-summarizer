import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """422 sem eco do valor enviado, para nunca devolver senhas.

    O erro padrão do FastAPI inclui ``input`` (o valor recebido; em campos
    ausentes, o corpo inteiro) e ``ctx``. Ambos são removidos.
    """
    errors = [
        {key: value for key, value in error.items() if key not in {"input", "ctx"}}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


async def database_operational_error_handler(
    request: Request, exc: OperationalError
) -> JSONResponse:
    """Retorna 503 JSON dentro do ExceptionMiddleware para preservar CORS."""
    logger.exception("Falha de conexão com o banco de dados")
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "Banco de dados indisponível. Verifique se o PostgreSQL está ativo "
                "e se DATABASE_URL aponta para o host correto (localhost:5434 fora "
                "do Docker ou db:5432 no Docker)."
            )
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(OperationalError, database_operational_error_handler)
