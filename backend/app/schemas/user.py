from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field(max_length=255)
    password: str = Field(
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
    picture_url: str | None = None

    model_config = ConfigDict(from_attributes=True)
