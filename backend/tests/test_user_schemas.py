from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from app.core.errors import register_exception_handlers
from app.schemas.user import PasswordChange, UserCreate, UserResponse, UserUpdate
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

VALID = {"name": "Ana Souza", "email": "ana@example.com", "password": "senha-segura-1"}


# ---------------------------------------------------------------- UserCreate
def test_valid_payload_is_accepted() -> None:
    payload = UserCreate(**VALID)

    assert payload.email == "ana@example.com"
    assert payload.password == "senha-segura-1"


def test_name_and_email_are_trimmed_but_the_password_is_not() -> None:
    payload = UserCreate(
        name="  Ana  ", email="  ana@example.com ", password="  espacos-ok  "
    )

    assert payload.name == "Ana"
    assert payload.email == "ana@example.com"
    assert payload.password == "  espacos-ok  "


def test_blank_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        UserCreate(**{**VALID, "name": "   "})


@pytest.mark.parametrize(
    "email", ["sem-arroba", "ana@", "@example.com", "ana@@example.com", "", "ana@localhost"]
)
def test_invalid_email_is_rejected(email: str) -> None:
    with pytest.raises(ValidationError):
        UserCreate(**{**VALID, "email": email})


@pytest.mark.parametrize(
    ("length", "valid"), [(7, False), (8, True), (128, True), (129, False)]
)
def test_password_length_limits(length: int, valid: bool) -> None:
    data = {**VALID, "password": "x" * length}
    if valid:
        assert UserCreate(**data)
    else:
        with pytest.raises(ValidationError):
            UserCreate(**data)


# ------------------------------------------------------------- UserResponse
def test_response_has_no_password_or_hash_fields() -> None:
    assert "hashed_password" not in UserResponse.model_fields
    assert "password" not in UserResponse.model_fields


def test_response_from_orm_object_drops_the_hash() -> None:
    user = SimpleNamespace(
        id=1,
        email="ana@example.com",
        name="Ana",
        is_active=True,
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$abc$def",
        created_at=datetime.now(timezone.utc),
    )

    body = UserResponse.model_validate(user).model_dump_json()

    assert "argon2" not in body
    assert "hashed_password" not in body


# -------------------------------------------------- extras de perfil (item 6)
def test_user_update_validates_name() -> None:
    assert UserUpdate(name=" Nova ").name == "Nova"
    with pytest.raises(ValidationError):
        UserUpdate(name="  ")


def test_password_change_requires_a_different_valid_password() -> None:
    assert PasswordChange(current_password="antiga-123", new_password="nova-senha-1")
    with pytest.raises(ValidationError, match="diferente da atual"):
        PasswordChange(current_password="mesma-senha-1", new_password="mesma-senha-1")
    with pytest.raises(ValidationError):
        PasswordChange(current_password="antiga-123", new_password="curta")


# ------------------------------------- 422 não pode devolver a senha enviada
@pytest.fixture
def mini_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/auth/register", status_code=201)
    def register(payload: UserCreate) -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def test_validation_error_does_not_echo_a_short_password(mini_client: TestClient) -> None:
    response = mini_client.post("/auth/register", json={**VALID, "password": "curta12"})

    assert response.status_code == 422
    assert "curta12" not in response.text


def test_validation_error_does_not_echo_the_password_when_another_field_fails(
    mini_client: TestClient,
) -> None:
    body = {"email": "ana@example.com", "password": "senha-valida-123"}  # sem nome

    response = mini_client.post("/auth/register", json=body)

    assert response.status_code == 422
    assert "senha-valida-123" not in response.text
    assert response.json()["detail"][0]["loc"] == ["body", "name"]


def test_valid_payload_passes_through_the_handler(mini_client: TestClient) -> None:
    assert mini_client.post("/auth/register", json=VALID).status_code == 201