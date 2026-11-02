from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=72,
        description="Senha deve conter entre 8 e 72 caracteres",
    )
    name: str = Field(min_length=2, max_length=255)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        max_length=72,
        description="Senha de acesso",
    )


class GoogleAuthRequest(BaseModel):
    credential: str


class UserPublic(BaseModel):
    id: int
    name: str
    picture_url: str | None = None

    model_config = ConfigDict(from_attributes=True)
