from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.dependencies.database_dependency import DatabaseSession
from app.dependencies.auth_dependency import get_current_active_user, require_admin_or_support
from app.middlewares.request_middleware import limiter
from app.schemas.loan_schema import LoanCreate, LoanDetailResponse, LoanResponse, LoanStatus
from app.services import loan_service

loan_router = APIRouter(prefix="/loans", tags=["Loans"])
NOT_FOUND = {404: {"description": "Préstamo no encontrado"}}
INTEGRITY_ERROR = {400: {"description": "Los datos incumplen una restricción de la base de datos"}}


@loan_router.get("", response_model=list[LoanResponse], status_code=status.HTTP_200_OK,
                 summary="Listar préstamos", description="Lista préstamos con filtros opcionales y combinables por status, user_email (búsqueda parcial) y device_type.",
                 response_description="Lista de préstamos")
def list_loans(db: DatabaseSession, status: LoanStatus | None = None,
               user_email: str | None = None, device_type: str | None = None):
    return loan_service.list_loans(
        db, status=status, user_email=user_email, device_type=device_type
    )


@loan_router.get("/details", dependencies=[Depends(require_admin_or_support)], response_model=list[LoanDetailResponse], status_code=status.HTTP_200_OK,
                 summary="Consultar detalles de préstamos", description="Lista los préstamos con su ID, estado y datos básicos del usuario y del dispositivo.",
                 response_description="Lista de préstamos con datos relacionados")
def list_loan_details(db: DatabaseSession):
    return loan_service.list_loan_details(db)


@loan_router.get("/{loan_id}", response_model=LoanResponse, status_code=status.HTTP_200_OK,
                 summary="Consultar préstamo por ID", description="Consulta un préstamo mediante su ID.",
                 response_description="Préstamo encontrado", responses=NOT_FOUND)
def get_loan(loan_id: int, db: DatabaseSession):
    loan = loan_service.find_loan(db, loan_id)
    if loan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Préstamo no encontrado")
    return loan


@loan_router.post("", dependencies=[Depends(get_current_active_user)], response_model=LoanResponse, status_code=status.HTTP_201_CREATED,
                  summary="Crear préstamo", description="Crea un préstamo con estado active y marca el dispositivo como no disponible, independientemente del estado recibido.",
                  response_description="Préstamo creado con ID generado por el servidor",
                  responses=INTEGRITY_ERROR | {
                      404: {"description": "Usuario o dispositivo no encontrado"},
                      409: {"description": "El dispositivo no está disponible"},
                  })
@limiter.limit("10/minute")
def create_loan(request: Request, data: LoanCreate, db: DatabaseSession):
    return loan_service.create_loan(db, data)


@loan_router.patch("/{loan_id}/return", dependencies=[Depends(require_admin_or_support)], response_model=LoanResponse, status_code=status.HTTP_200_OK,
                   summary="Devolver dispositivo", description="Registra la devolución del préstamo y restablece la disponibilidad del dispositivo.",
                   response_description="Préstamo devuelto con fecha de devolución registrada",
                   responses=INTEGRITY_ERROR | {
                       404: {"description": "Préstamo o dispositivo no encontrado"},
                       409: {"description": "El préstamo ya fue devuelto"},
                   })
def return_loan(loan_id: int, db: DatabaseSession):
    return loan_service.return_loan(db, loan_id)
