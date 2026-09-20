"""CRUD SQLAlchemy de dispositivos con protección contra seriales duplicados."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.device_model import Device
# Registrar los modelos referenciados por las relaciones de Device y Loan.
from app.models.loan_model import Loan
from app.models.user_model import User
from app.schemas.device_schema import DeviceCreate, DeviceUpdate


def find_device(db: Session, device_id: int) -> Device | None:
    return db.get(Device, device_id)


def find_device_by_serial_number(db: Session, serial_number: str) -> Device | None:
    return db.scalar(select(Device).where(Device.serial_number == serial_number))


def check_duplicate_serial_number(db: Session, serial_number: str, exclude_id: int | None = None):
    existing = find_device_by_serial_number(db, serial_number)
    if existing is not None and existing.id != exclude_id:
        raise HTTPException(400, "El número de serie ya está registrado")


def list_devices(db: Session, device_type=None, is_available=None, brand=None, search=None):
    query = select(Device)
    if device_type is not None:
        query = query.where(Device.device_type == device_type)
    if is_available is not None:
        query = query.where(Device.is_available == is_available)
    if brand is not None:
        query = query.where(Device.brand == brand)
    if search is not None:
        query = query.where(Device.name.icontains(search, autoescape=True))
    return db.scalars(query.order_by(Device.name, Device.id)).all()


def _commit(db: Session):
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if "UNIQUE constraint failed: devices.serial_number" in str(error.orig):
            raise HTTPException(400, "El número de serie ya está registrado") from error
        raise HTTPException(400, "Los datos incumplen una restricción de la base de datos") from error


def create_device(db: Session, data: DeviceCreate) -> Device:
    check_duplicate_serial_number(db, data.serial_number)
    device = Device(**data.model_dump())
    db.add(device)
    _commit(db)
    db.refresh(device)
    return device


def _apply_changes(db: Session, device: Device, values: dict) -> Device:
    if "serial_number" in values:
        check_duplicate_serial_number(db, values["serial_number"], exclude_id=device.id)
    for field, value in values.items():
        setattr(device, field, value)
    _commit(db)
    db.refresh(device)
    return device


def update_device(db: Session, device: Device, data: DeviceUpdate) -> Device:
    return _apply_changes(db, device, data.model_dump())


def patch_device(db: Session, device: Device, data: dict) -> Device:
    if not data:
        raise HTTPException(400, "Debe enviar al menos un campo para actualizar")
    current = {field: getattr(device, field) for field in DeviceUpdate.model_fields}
    validated = DeviceUpdate.model_validate(current | data).model_dump()
    values = {field: validated[field] for field in data}
    return _apply_changes(db, device, values)


def delete_device(db: Session, device: Device) -> None:
    db.delete(device)
    _commit(db)
