"""Validación Pydantic v2; las contraseñas no se serializan."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator, model_validator

from app.schemas.user_schema import UserName, UserRole


class UserRegister(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    name: UserName = Field(description="Nombre de al menos 3 caracteres")
    email: EmailStr = Field(description="Correo único")
    password: SecretStr = Field(min_length=8, max_length=1024, exclude=True)
    role: UserRole = Field(default="user", description="admin, support o user (actividad EV11)")

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: SecretStr) -> SecretStr:
        password = value.get_secret_value()
        if (any(c.isspace() for c in password)
                or not any(c.isupper() for c in password)
                or not any(c.islower() for c in password)
                or not any(c.isdigit() for c in password)):
            raise ValueError("La contraseña requiere mayúscula, minúscula, número y ningún espacio")
        return value


class UserLogin(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    email: EmailStr = Field(description="Correo registrado; username en el formulario OAuth2")
    password: SecretStr = Field(min_length=1, max_length=1024, exclude=True)


class Token(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    access_token: str = Field(min_length=1)
    token_type: Literal["bearer"] = "bearer"


class TokenData(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    sub: str = Field(pattern=r"^[1-9][0-9]*$", max_length=19)
    exp: int = Field(gt=0)
    iat: int = Field(gt=0)

    @model_validator(mode="after")
    def valid_lifetime(self):
        if self.exp <= self.iat or int(self.sub) > 9223372036854775807:
            raise ValueError("Claims del token inválidos")
        return self
