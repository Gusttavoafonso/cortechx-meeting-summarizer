import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não foi configurada.")

#engine: responsável pela conexão com o PostgreSQL
engine = create_engine(
    DATABASE_URL,
    echo=False,
)

#SessionLocal: responsável por criar sessões para operações no banco;
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

#Base: classe base usada pelos models.
class Base(DeclarativeBase):
    pass


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


# Importa os models para registrá-los no Base.metadata.
# Isso será utilizado pelo Alembic para gerar as migrations.
import app.models  # noqa: E402, F401