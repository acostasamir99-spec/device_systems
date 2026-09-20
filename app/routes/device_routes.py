from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.dependencies.auth_dependency import require_admin, require_admin_or_support
from app.models.device_model import Device
from app.dependencies.database_dependency import DatabaseSession
from app.schemas.device_schema import DeviceCreate, DeviceResponse, DeviceUpdate
from app.schemas.loan_schema import LoanResponse
from app.services import device_service, loan_service

device_router = APIRouter(prefix="/devices", tags=["Devices"])
NOT_FOUND = {404: {"description": "Dispositivo no encontrado"}}
WRITE_ERROR = {400: {"description": "Serial duplicado o incumplimiento de una restricción de integridad"}}
PATCH_ERROR = {400: {"description": "Serial duplicado, PATCH vacío o incumplimiento de una restricción de integridad"}}
DELETE_ERROR = {400: {"description": "La eliminación incumple una restricción de integridad"}}


def get_device_or_404(device_id: int, db: DatabaseSession) -> Device:
    device = device_service.find_device(db, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dispositivo no encontrado")
    return device


ExistingDevice = Annotated[Device, Depends(get_device_or_404)]


@device_router.get("", response_model=list[DeviceResponse], status_code=status.HTTP_200_OK,
                   summary="Listar dispositivos", description="Lista dispositivos con filtros combinables por device_type, is_available, brand y search sobre el nombre.",
                   response_description="Dispositivos que cumplen los filtros")
def list_devices(db: DatabaseSession, device_type: str | None = None,
                 is_available: bool | None = None, brand: str | None = None,
                 search: str | None = None):
    return device_service.list_devices(db, device_type, is_available, brand, search)


@device_router.get("/{device_id}", response_model=DeviceResponse, status_code=status.HTTP_200_OK,
                   summary="Consultar dispositivo por ID", description="Consulta un dispositivo mediante su ID.",
                   response_description="Dispositivo encontrado", responses=NOT_FOUND)
def get_device(device: ExistingDevice):
    return device


@device_router.get("/{device_id}/loans", response_model=list[LoanResponse], status_code=status.HTTP_200_OK,
                   summary="Consultar historial de préstamos del dispositivo", description="Lista los préstamos del dispositivo. Devuelve una lista vacía si existe y nunca ha sido prestado.",
                   response_description="Historial de préstamos del dispositivo", responses=NOT_FOUND)
def list_device_loans(device_id: int, db: DatabaseSession):
    return loan_service.list_loans_by_device(db, device_id)


@device_router.post("", dependencies=[Depends(require_admin_or_support)], response_model=DeviceResponse, status_code=status.HTTP_201_CREATED,
                    summary="Crear dispositivo", description="Crea un dispositivo con número de serie único.",
                    response_description="Dispositivo creado con ID generado por el servidor", responses=WRITE_ERROR)
def create_device(data: DeviceCreate, db: DatabaseSession):
    return device_service.create_device(db, data)


@device_router.put("/{device_id}", dependencies=[Depends(require_admin_or_support)], response_model=DeviceResponse, status_code=status.HTTP_200_OK,
                   summary="Actualizar dispositivo completamente", description="Reemplaza los campos editables; conserva el ID y la fecha de creación.",
                   response_description="Dispositivo actualizado", responses=NOT_FOUND | WRITE_ERROR)
def update_device(data: DeviceUpdate, device: ExistingDevice, db: DatabaseSession):
    return device_service.update_device(db, device, data)


@device_router.patch("/{device_id}", response_model=DeviceResponse, status_code=status.HTTP_200_OK,
                     summary="Actualizar dispositivo parcialmente", description="Modifica únicamente los campos enviados. Rechaza campos adicionales y objetos vacíos; solo brand admite null.",
                     response_description="Dispositivo actualizado parcialmente", responses=NOT_FOUND | PATCH_ERROR)
def patch_device(data: dict, device: ExistingDevice, db: DatabaseSession):
    try:
        return device_service.patch_device(db, device, data)
    except ValidationError as error:
        errors = [
            {**item, "loc": ("body", *item["loc"])}
            for item in error.errors()
        ]
        raise RequestValidationError(errors, body=data) from error


@device_router.delete("/{device_id}", dependencies=[Depends(require_admin)], status_code=status.HTTP_204_NO_CONTENT,
                      summary="Eliminar dispositivo", description="Elimina el dispositivo de la base de datos.",
                      response_description="Dispositivo eliminado; respuesta sin cuerpo", responses=NOT_FOUND | DELETE_ERROR)
def delete_device(device: ExistingDevice, db: DatabaseSession) -> Response:
    device_service.delete_device(db, device)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
