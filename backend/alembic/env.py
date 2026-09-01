import asyncio
import os
import sys

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config


# Garante que "app" seja importável
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.database import Base


# Carrega o .env que fica fora de /backend
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


# Objeto de configuração do Alembic
config = context.config


# Pega a DATABASE_URL do ambiente/.env
database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise RuntimeError("DATABASE_URL não foi configurada.")


# Passa a URL para o Alembic
config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("%", "%%"),
)


# Configuração de logs do Alembic
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Metadata dos models SQLAlchemy
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Executa migrations sem criar uma conexão com o banco."""

    url = database_url

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Executa as migrations usando uma conexão existente."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Cria o engine assíncrono e executa as migrations."""

    connectable = async_engine_from_config(
        config.get_section(
            config.config_ini_section,
            {}
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Executa migrations conectando ao banco."""

    if sys.platform == "win32":
        asyncio.run(
            run_async_migrations(),
            loop_factory=asyncio.SelectorEventLoop,
        )
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()