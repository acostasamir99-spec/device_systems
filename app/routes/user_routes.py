from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status

from app.dependencies.auth_dependency import get_current_active_user
from app.middlewares.request_middleware import limiter
from app.models.user_model import User
from app.dependencies.database_dependency import DatabaseSession
from app.schemas.user_schema import UserRole
from app.dependencies.user_dependencies import get_user_or_404
from app.schemas.user_schema import UserCreate, UserPatch, UserResponse, UserUpdate
from app.schemas.loan_schema import LoanResponse
from app.services import loan_service, user_service

user_router = APIRouter(prefix="/users", tags=["Users"])
ExistingUser = Annotated[User, Depends(get_user_or_404)]
NOT_FOUND = {404: {"description": "Usuario no encontrado"}}
WRITE_ERROR = {400: {"description": "Correo duplicado o incumplimiento de una restricción de integridad"}}
PATCH_ERROR = {400: {"description": "Correo duplicado, PATCH vacío o incumplimiento de una restricción de integridad"}}
DELETE_ERROR = {400: {"description": "La eliminación incumple una restricción de integridad"}}


@user_router.get("", dependencies=[Depends(get_current_active_user)], response_model=list[UserResponse], status_code=status.HTTP_200_OK,
                 summary="Listar usuarios", description="Lista usuarios y permite combinar role e is_active; ordenar con sort_by (name/created_at) y order (asc/desc).",
                 response_description="Usuarios que cumplen los filtros")
@limiter.limit("30/minute")
def list_users(request: Request, db: DatabaseSession, role: UserRole | None = None, is_active: bool | None = None,
               sort_by: Literal["name", "created_at"] = "name",
               order: Literal["asc", "desc"] = "asc"):
    return user_service.list_users(db, role, is_active, sort_by, order)


@user_router.get("/{user_id}", dependencies=[Depends(get_current_active_user)], response_model=UserResponse, status_code=status.HTTP_200_OK,
                 summary="Consultar usuario por ID", description="Consulta un usuario mediante su ID.",
                 response_description="Usuario encontrado", responses=NOT_FOUND)
def get_user(user: ExistingUser):
    return user


@user_router.get("/{user_id}/loans", response_model=list[LoanResponse], status_code=status.HTTP_200_OK,
                 summary="Consultar historial de préstamos del usuario", description="Lista los préstamos del usuario. Devuelve una lista vacía si existe y no tiene préstamos.",
                 response_description="Historial de préstamos del usuario", responses=NOT_FOUND)
def list_user_loans(user_id: int, db: DatabaseSession):
    return loan_service.list_loans_by_user(db, user_id)


@user_router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED,
                  summary="Crear usuario", description="Crea un usuario con correo único y rol admin, support o user.",
                  response_description="Usuario creado con ID generado por el servidor", responses=WRITE_ERROR)
def create_user(data: UserCreate, db: DatabaseSession):
    return user_service.create_user(db, data)


@user_router.put("/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK,
                 summary="Actualizar usuario completamente", description="Reemplaza los cuatro campos editables; conserva el ID.",
                 response_description="Usuario actualizado", responses=NOT_FOUND | WRITE_ERROR)
def update_user(data: UserUpdate, user: ExistingUser, db: DatabaseSession):
    return user_service.update_user(db, user, data)


@user_router.patch("/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK,
                   summary="Actualizar usuario parcialmente", description="Modifica únicamente los campos enviados. No admite null ni un objeto vacío.",
                   response_description="Usuario actualizado parcialmente", responses=NOT_FOUND | PATCH_ERROR)
def patch_user(data: UserPatch, user: ExistingUser, db: DatabaseSession):
    return user_service.patch_user(db, user, data)


@user_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT,
                    summary="Eliminar usuario", description="Elimina el usuario de la base de datos.",
                    response_description="Usuario eliminado; respuesta sin cuerpo", responses=NOT_FOUND | DELETE_ERROR)
def delete_user(user: ExistingUser, db: DatabaseSession) -> Response:
    user_service.delete_user(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
