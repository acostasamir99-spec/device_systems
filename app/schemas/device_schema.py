"""Validación de dispositivos con Pydantic v2."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeviceCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "name": "Laptop Lenovo ThinkPad",
                "serial_number": "LEN-2024-001",
                "device_type": "laptop",
                "brand": "Lenovo",
                "is_available": True
            }
        },
    )

    name: str
    serial_number: str
    device_type: str
    brand: str | None = None
    is_available: bool = True


class DeviceUpdate(DeviceCreate):
    is_available: bool


class DeviceResponse(DeviceCreate):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "id": 3,
                "name": "Laptop Lenovo ThinkPad",
                "serial_number": "LEN-2024-001",
                "device_type": "laptop",
                "brand": "Lenovo",
                "is_available": True,
                "created_at": "2026-09-17T10:00:00"
            }
        },
    )
    id: int
    created_at: datetime
