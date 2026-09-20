"""Registro y autenticación reutilizando las transacciones del CRUD."""
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, generate_unusable_password_hash, get_password_hash, verify_password
from app.models.user_model import User
from app.schemas.auth_schema import Token, UserLogin, UserRegister
from app.services import user_service


@lru_cache(maxsize=1)
def _dummy_hash():
    return generate_unusable_password_hash()


def register_user(db: Session, data: UserRegister) -> User:
    user_service.check_duplicate_email(db, str(data.email))
    user = User(name=data.name, email=str(data.email), role=data.role,
                hashed_password=get_password_hash(data.password.get_secret_value()))
    db.add(user)
    user_service._commit(db)
    db.refresh(user)
    return user


def login_user(db: Session, data: UserLogin) -> Token:
    user = user_service.find_user_by_email(db, str(data.email))
    valid = verify_password(data.password.get_secret_value(),
                            user.hashed_password if user else _dummy_hash())
    if not valid or user is None:
        raise HTTPException(401, "Correo o contraseña incorrectos", headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise HTTPException(403, "Usuario inactivo")
    return Token(access_token=create_access_token({"sub": str(user.id)}))
