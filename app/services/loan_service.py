"""Creación y devolución de préstamos con persistencia SQLAlchemy."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, contains_eager

from app.models.user_model import User
from app.models.device_model import Device
from app.models.loan_model import Loan
from app.schemas.loan_schema import LoanCreate


def list_loans(db: Session, status: str | None = None,
               user_email: str | None = None, device_type: str | None = None):
    query = select(Loan)
    conditions = []
    if status is not None:
        conditions.append(Loan.status == status)
    if user_email is not None:
        query = query.join(Loan.user)
        # Búsqueda parcial por correo; % y _ se interpretan como texto literal.
        email = user_email.replace("/", "//").replace("%", "/%").replace("_", "/_")
        conditions.append(User.email.ilike(f"%{email}%", escape="/"))
    if device_type is not None:
        query = query.join(Loan.device)
        conditions.append(Device.device_type == device_type)
    if conditions:
        query = query.where(and_(*conditions))
    return db.scalars(query.order_by(Loan.id)).all()


def list_loan_details(db: Session):
    query = (
        select(Loan)
        .join(Loan.user)
        .join(Loan.device)
        .options(contains_eager(Loan.user), contains_eager(Loan.device))
        .order_by(Loan.id)
    )
    return db.scalars(query).all()


def list_loans_by_user(db: Session, user_id: int):
    if db.get(User, user_id) is None:
        raise HTTPException(404, "Usuario no encontrado")
    query = select(Loan).where(Loan.user_id == user_id).order_by(Loan.id)
    return db.scalars(query).all()


def list_loans_by_device(db: Session, device_id: int):
    if db.get(Device, device_id) is None:
        raise HTTPException(404, "Dispositivo no encontrado")
    query = select(Loan).where(Loan.device_id == device_id).order_by(Loan.id)
    return db.scalars(query).all()


def find_loan(db: Session, loan_id: int) -> Loan | None:
    return db.get(Loan, loan_id)


def _commit(db: Session):
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(400, "Los datos incumplen una restricción de la base de datos") from error
    except SQLAlchemyError:
        db.rollback()
        raise


def create_loan(db: Session, data: LoanCreate) -> Loan:
    user = db.get(User, data.user_id)
    if user is None:
        raise HTTPException(404, "Usuario no encontrado")
    device = db.get(Device, data.device_id)
    if device is None:
        raise HTTPException(404, "Dispositivo no encontrado")
    if not device.is_available:
        raise HTTPException(409, "El dispositivo no está disponible")

    loan = Loan(user_id=user.id, device_id=device.id, status="active")
    db.add(loan)
    device.is_available = False
    # El préstamo y la disponibilidad se guardan en la misma transacción.
    _commit(db)
    db.refresh(loan)
    return loan


def return_loan(db: Session, loan_id: int) -> Loan:
    loan = find_loan(db, loan_id)
    if loan is None:
        raise HTTPException(404, "Préstamo no encontrado")
    if loan.status == "returned" or loan.return_date is not None:
        raise HTTPException(409, "El préstamo ya fue devuelto")
    device = db.get(Device, loan.device_id)
    if device is None:
        raise HTTPException(404, "Dispositivo no encontrado")

    loan.status = "returned"
    loan.return_date = datetime.now(timezone.utc).replace(tzinfo=None)
    device.is_available = True
    # La devolución y la disponibilidad se guardan en la misma transacción.
    _commit(db)
    db.refresh(loan)
    return loan
