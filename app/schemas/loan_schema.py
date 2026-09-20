"""Validación de préstamos con Pydantic v2."""

from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field


LoanStatus = Literal["active", "returned", "overdue"]


class LoanCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "user_id": 1,
                "device_id": 3,
                "status": "active"
            }
        },
    )

    user_id: int
    device_id: int
    status: LoanStatus


class LoanUpdate(LoanCreate):
    return_date: datetime | None = None


class LoanResponse(LoanCreate):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "id": 1,
                "user_id": 1,
                "device_id": 3,
                "status": "returned",
                "loan_date": "2026-09-17T11:00:00",
                "return_date": "2026-09-18T11:00:00"
            }
        },
    )
    id: int
    loan_date: datetime
    return_date: datetime | None


class _LoanUserResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Ana Pérez",
                "email": "ana@sena.edu.co"
            }
        },
    )

    id: int
    name: str
    email: EmailStr


class _LoanDeviceResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "id": 3,
                "name": "Laptop Lenovo ThinkPad",
                "serial_number": "LEN-2024-001",
                "device_type": "laptop"
            }
        },
    )

    id: int
    name: str
    serial_number: str
    device_type: str


class LoanDetailResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "loan_id": 1,
                "status": "active",
                "user": {
                    "id": 1,
                    "name": "Ana Pérez",
                    "email": "ana@sena.edu.co"
                },
                "device": {
                    "id": 3,
                    "name": "Laptop Lenovo ThinkPad",
                    "serial_number": "LEN-2024-001",
                    "device_type": "laptop"
                }
            }
        },
    )

    loan_id: int = Field(validation_alias=AliasChoices("loan_id", "id"))
    status: LoanStatus
    user: _LoanUserResponse
    device: _LoanDeviceResponse
