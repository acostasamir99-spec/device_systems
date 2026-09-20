"""Autenticación Bearer y permisos consultados en la base en cada petición."""
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from pydantic import ValidationError

from app.auth.security import decode_access_token
from app.dependencies.database_dependency import DatabaseSession
from app.models.user_model import User
from app.schemas.auth_schema import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def get_current_user(db: DatabaseSession, token: Annotated[str | None, Depends(oauth2_scheme)]) -> User:
    unauthorized = HTTPException(401, "No autenticado o token inválido", headers={"WWW-Authenticate": "Bearer"})
    if not token:
        raise unauthorized
    try:
        data = TokenData.model_validate(decode_access_token(token))
    except (JWTError, ValidationError, ValueError, TypeError):
        raise unauthorized from None
    user = db.get(User, int(data.sub))
    if user is None:
        raise unauthorized
    return user


def get_current_active_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_active:
        raise HTTPException(403, "Usuario inactivo")
    return user


CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]


def require_admin(user: CurrentActiveUser) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Se requiere rol admin")
    return user


def require_admin_or_support(user: CurrentActiveUser) -> User:
    if user.role not in {"admin", "support"}:
        raise HTTPException(403, "Se requiere rol admin o support")
    return user
