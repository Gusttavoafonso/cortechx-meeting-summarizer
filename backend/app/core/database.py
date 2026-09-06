from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# Engine: responsável pela conexão com o PostgreSQL.
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
)

# SessionLocal: responsável por criar sessões para operações no banco.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# Base: classe base usada pelos models.
class Base(DeclarativeBase):
    pass


# Garante que a sessão seja fechada após o uso.
def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


# Importa os models para registrá-los no Base.metadata.
# Isso será utilizado pelo Alembic para gerar as migrations.
import app.models  # noqa: E402, F401