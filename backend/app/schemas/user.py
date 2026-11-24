from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StringConstraints,
    model_validator,
)

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class UserCreate(BaseModel):
    # Só nome e e-mail são limpos. A senha nunca é "stripada": um espaço digitado
    # no cadastro precisa valer igual no login.
    name: Name
    email: EmailStr = Field(max_length=255)
    password: SecretStr = Field(
        min_length=8,
        max_length=128,
        description="Mínimo de 8 caracteres",
    )


class UserResponse(BaseModel):
    """Dados do usuário. Nunca expõe o hash da senha."""

    id: int
    name: str
    email: str
    is_active: bool
    picture_url: str | None = None
    has_password: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class GoogleAuthRequest(BaseModel):
    credential: str


class UserPublic(BaseModel):
    id: int
    name: str
    email: str
    picture_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    name: Name


class PasswordChange(BaseModel):
    current_password: SecretStr
    new_password: SecretStr = Field(
        min_length=8,
        max_length=128,
        description="Mínimo de 8 caracteres",
    )

    @model_validator(mode="after")
    def new_password_must_differ(self) -> "PasswordChange":
        if (
            self.new_password.get_secret_value()
            == self.current_password.get_secret_value()
        ):
            raise ValueError("A nova senha deve ser diferente da atual.")
        return self