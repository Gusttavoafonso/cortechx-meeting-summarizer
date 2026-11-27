import pytest
from app.core.exceptions import InvalidCredentialsError
from app.services.auth_service import (
    authenticate_with_credentials,
    get_or_create_google_user,
    register_user,
)


def test_google_login_discards_a_password_set_before_the_owner_proved_the_email(
    db_session,
) -> None:
    # Cadastro por e-mail/senha não verifica o dono do e-mail. Se alguém cadastra
    # o e-mail de outra pessoa e ela depois entra com Google, a senha antiga não
    # pode continuar abrindo a conta.
    register_user(
        db_session,
        email="vitima@example.com",
        password="senha-do-atacante-1",
        name="Atacante",
    )

    user = get_or_create_google_user(
        db_session,
        google_sub="google-vitima",
        email="vitima@example.com",
        name="Vítima Real",
    )

    assert user.google_id == "google-vitima"
    assert user.hashed_password is None
    with pytest.raises(InvalidCredentialsError):
        authenticate_with_credentials(
            db_session, "vitima@example.com", "senha-do-atacante-1"
        )