"""Posse e autorização das reuniões.

Cobre o contrato da issue #40: toda rota de ``/meetings`` exige sessão válida,
cada usuário só alcança as próprias reuniões e a reunião de outro responde 404
(e não 403, para não revelar que ela existe).
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.api.v1.meetings import (
    get_diarization_service,
    get_meeting_job_dispatcher,
    get_summary_service,
    get_transcription_service,
)
from app.core.config import settings
from app.core.database import Base
from app.main import app
from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.models.user import User
from app.repositories.meeting_repository import MeetingRepository
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

AUDIO_UPLOAD = {"files": {"file": ("reuniao.wav", b"RIFF0000WAVE", "audio/wav")}}

# Todas as rotas de reunião que recebem um ``meeting_id``.
MEETING_ROUTES = [
    ("detalhar", "get", "/meetings/{id}", {}),
    ("upload-audio", "post", "/meetings/{id}/audio", AUDIO_UPLOAD),
    ("metadados-audio", "get", "/meetings/{id}/audio", {}),
    ("transcrever", "post", "/meetings/{id}/transcribe", {}),
    ("diarizar", "post", "/meetings/{id}/diarize", {}),
    ("transcript", "get", "/meetings/{id}/transcript", {}),
    ("processar", "post", "/meetings/{id}/process", {}),
    ("criar-resumo", "post", "/meetings/{id}/summary", {}),
    ("consultar-resumo", "get", "/meetings/{id}/summary", {}),
    ("retry", "post", "/meetings/{id}/retry", {}),
    ("status", "get", "/meetings/{id}/status", {}),
    ("integracoes", "get", "/meetings/{id}/integrations", {}),
    ("retry-integracoes", "post", "/meetings/{id}/integrations/retry", {}),
]

# Rotas da coleção, sem ``meeting_id``.
COLLECTION_ROUTES = [
    ("criar", "post", "/meetings", {"json": {"title": "Reunião"}}),
    ("listar", "get", "/meetings", {}),
]

ALL_ROUTES = COLLECTION_ROUTES + MEETING_ROUTES


def _ids(routes: list[tuple]) -> list[str]:
    return [route[0] for route in routes]


def _call(client: TestClient, method: str, path: str, kwargs: dict):
    return getattr(client, method)(path, **kwargs)


class _UnusableService:
    """Stub cujo uso significa que a rota passou da checagem de posse."""

    def __getattr__(self, name: str) -> Callable[..., None]:
        def _fail(*_args, **_kwargs):
            raise AssertionError(
                f"{name}() foi chamado em uma reunião que não é do usuário"
            )

        return _fail


@pytest.fixture
def stub_services(_api_database: None) -> None:
    """Neutraliza STT, diarização, LLM e fila.

    As dependências são resolvidas antes do corpo da rota, então precisam
    existir; qualquer uso efetivo delas levanta AssertionError. Os overrides
    são limpos no teardown de `_api_database`.
    """

    def _unusable():
        return _UnusableService()

    def _dispatcher():
        def _enqueue(*_args, **_kwargs):
            raise AssertionError("job enfileirado para reunião de outro usuário")

        return _enqueue

    app.dependency_overrides[get_transcription_service] = _unusable
    app.dependency_overrides[get_diarization_service] = _unusable
    app.dependency_overrides[get_summary_service] = _unusable
    app.dependency_overrides[get_meeting_job_dispatcher] = _dispatcher


def _persist_meeting(
    db: Session,
    owner: User | None,
    title: str = "Reunião",
    status: MeetingStatus = MeetingStatus.RECEIVED,
) -> Meeting:
    meeting = Meeting(
        title=title,
        status=status,
        user_id=owner.id if owner is not None else None,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


@pytest.fixture
def user_a(create_user: Callable[..., User]) -> User:
    return create_user(email="a@cortechx.com", name="Usuário A")


@pytest.fixture
def user_b(create_user: Callable[..., User]) -> User:
    return create_user(email="b@cortechx.com", name="Usuário B")


@pytest.fixture
def meeting_of_a(db_session: Session, user_a: User) -> Meeting:
    return _persist_meeting(db_session, user_a, title="Reunião confidencial do A")


@pytest.fixture
def client_b(
    authenticate: Callable[[User], TestClient],
    user_b: User,
) -> TestClient:
    return authenticate(user_b)


# ---------------------------------------------------------------------------
# Posse na criação e na listagem
# ---------------------------------------------------------------------------


def test_reuniao_criada_recebe_o_usuario_autenticado(
    auth_client: TestClient,
    db_session: Session,
    test_user: User,
) -> None:
    response = auth_client.post("/meetings", json={"title": "Planejamento"})

    assert response.status_code == 201
    created = db_session.get(Meeting, response.json()["id"])
    assert created.user_id == test_user.id
    assert created.owner.id == test_user.id


def test_listagem_retorna_apenas_as_reunioes_do_usuario(
    db_session: Session,
    authenticate: Callable[[User], TestClient],
    user_a: User,
    user_b: User,
) -> None:
    da_a = _persist_meeting(db_session, user_a, title="Da A")
    da_b = _persist_meeting(db_session, user_b, title="Da B")

    listadas = authenticate(user_a).get("/meetings").json()
    ids = [meeting["id"] for meeting in listadas]

    assert ids == [da_a.id]
    assert da_b.id not in ids


# ---------------------------------------------------------------------------
# Isolamento entre usuários: 404 em todas as rotas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [route[1:] for route in MEETING_ROUTES],
    ids=_ids(MEETING_ROUTES),
)
def test_usuario_nao_alcanca_reuniao_de_outro(
    stub_services: None,
    client_b: TestClient,
    meeting_of_a: Meeting,
    method: str,
    path: str,
    kwargs: dict,
) -> None:
    """B recebe 404 — e não 403 — em cada rota da reunião de A."""
    response = _call(client_b, method, path.format(id=meeting_of_a.id), kwargs)

    assert response.status_code == 404, response.text
    assert "não encontrada" in response.json()["detail"]


def test_reuniao_de_outro_nao_e_alterada_pela_tentativa_de_acesso(
    stub_services: None,
    client_b: TestClient,
    db_session: Session,
    meeting_of_a: Meeting,
) -> None:
    """Nenhuma rota chamada por B muda o estado da reunião de A."""
    for _, method, path, kwargs in MEETING_ROUTES:
        _call(client_b, method, path.format(id=meeting_of_a.id), kwargs)

    db_session.refresh(meeting_of_a)
    assert MeetingStatus(meeting_of_a.status) == MeetingStatus.RECEIVED
    assert meeting_of_a.audio is None


# ---------------------------------------------------------------------------
# Sessão ausente ou inválida: 401 em todas as rotas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [route[1:] for route in ALL_ROUTES],
    ids=_ids(ALL_ROUTES),
)
def test_rota_de_reuniao_sem_token_responde_401(
    stub_services: None,
    client: TestClient,
    method: str,
    path: str,
    kwargs: dict,
) -> None:
    response = _call(client, method, path.format(id=1), kwargs)

    assert response.status_code == 401, response.text


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [route[1:] for route in ALL_ROUTES],
    ids=_ids(ALL_ROUTES),
)
def test_rota_de_reuniao_com_token_invalido_responde_401(
    stub_services: None,
    client: TestClient,
    method: str,
    path: str,
    kwargs: dict,
) -> None:
    client.cookies.set(settings.session_cookie_name, "token-forjado")

    response = _call(client, method, path.format(id=1), kwargs)

    assert response.status_code == 401, response.text


def test_health_permanece_publico(client: TestClient) -> None:
    assert client.get("/health").status_code == 200


# ---------------------------------------------------------------------------
# Reuniões anteriores ao controle de posse (user_id nulo)
# ---------------------------------------------------------------------------


def test_reuniao_sem_dono_nao_e_acessivel(
    stub_services: None,
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Reunião antiga, sem dono, não pertence a ninguém: 404 em toda rota."""
    orfa = _persist_meeting(db_session, None, title="Reunião legada")

    for _, method, path, kwargs in MEETING_ROUTES:
        response = _call(auth_client, method, path.format(id=orfa.id), kwargs)
        assert response.status_code == 404, f"{method} {path}: {response.text}"


def test_reuniao_sem_dono_nao_aparece_na_listagem(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    orfa = _persist_meeting(db_session, None, title="Reunião legada")

    listadas = auth_client.get("/meetings").json()

    assert orfa.id not in [meeting["id"] for meeting in listadas]


# ---------------------------------------------------------------------------
# Pipeline interno: o worker não depende de usuário
# ---------------------------------------------------------------------------


def test_worker_alcanca_a_reuniao_sem_filtro_de_posse(
    db_session: Session,
    user_a: User,
) -> None:
    """O worker recebe só o meeting_id; a posse já foi validada na API."""
    repository = MeetingRepository(db_session)
    da_a = _persist_meeting(db_session, user_a)
    orfa = _persist_meeting(db_session, None)

    assert repository.get_for_pipeline(da_a.id).id == da_a.id
    assert repository.get_for_pipeline(orfa.id).id == orfa.id
    assert repository.try_claim_processing(da_a.id) is True


def test_consulta_por_posse_ignora_reuniao_de_outro_e_sem_dono(
    db_session: Session,
    user_a: User,
    user_b: User,
) -> None:
    repository = MeetingRepository(db_session)
    da_a = _persist_meeting(db_session, user_a)
    orfa = _persist_meeting(db_session, None)

    assert repository.get_by_id(da_a.id, user_a.id).id == da_a.id
    assert repository.get_by_id(da_a.id, user_b.id) is None
    assert repository.get_by_id(orfa.id, user_a.id) is None
    assert repository.list_all(user_b.id) == []


# ---------------------------------------------------------------------------
# Esquema: RESTRICT e head única de migrations
# ---------------------------------------------------------------------------


def test_fk_de_posse_usa_restrict() -> None:
    """CASCADE apagaria as linhas mas não os áudios já gravados em disco."""
    foreign_key = next(iter(Meeting.__table__.c.user_id.foreign_keys))

    assert foreign_key.column.table.name == "users"
    assert foreign_key.ondelete == "RESTRICT"


def test_banco_impede_excluir_usuario_com_reunioes() -> None:
    """Com as FKs ativas, o RESTRICT barra a exclusão do dono."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        dono = User(email="dono@cortechx.com", name="Dono")
        session.add(dono)
        session.commit()
        session.add(Meeting(title="Com dono", user_id=dono.id))
        session.commit()

        session.delete(dono)
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_migrations_tem_uma_unica_head() -> None:
    """Um branch de migrations faria `alembic upgrade head` falhar."""
    backend_dir = Path(__file__).resolve().parents[1]
    script = ScriptDirectory.from_config(Config(str(backend_dir / "alembic.ini")))

    assert len(script.get_heads()) == 1
