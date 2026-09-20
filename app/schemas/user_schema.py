"""Validación de datos con Pydantic v2; roles restringidos en los schemas."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints, field_validator

UserName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3)]


UserRole = Literal["admin", "support", "user"]


class UserBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "name": "Ana Pérez",
                "email": "ana@sena.edu.co",
                "role": "user",
                "is_active": True
            }
        },
    )

    name: UserName
    email: EmailStr
    role: UserRole
    is_active: bool = True


class UserCreate(UserBase):
    """El cliente no puede enviar un ID."""


class UserUpdate(UserBase):
    is_active: bool


class UserPatch(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "is_active": False
            }
        },
    )

    name: UserName | None = None
    email: EmailStr | None = None
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("name", "email", "role", "is_active", mode="before")
    @classmethod
    def reject_explicit_null(cls, value):
        # Omitir un campo es válido; enviar null no debe borrar datos requeridos.
        if value is None:
            raise ValueError("El campo no admite null")
        return value


class UserResponse(UserBase):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Ana Pérez",
                "email": "ana@sena.edu.co",
                "role": "user",
                "is_active": True,
                "created_at": "2026-09-17T10:00:00"
            }
        },
    )
    id: int
    created_at: datetime
