"""Registro JSON y login OAuth2 (formulario) o JSON."""
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError

from app.auth import auth_service
from app.dependencies.auth_dependency import CurrentActiveUser
from app.dependencies.database_dependency import DatabaseSession
from app.middlewares.request_middleware import limiter
from app.schemas.auth_schema import Token, UserLogin, UserRegister
from app.schemas.user_schema import UserResponse

auth_router = APIRouter(prefix="/auth", tags=["Auth"])


async def login_payload(request: Request) -> UserLogin:
    try:
        if request.headers.get("content-type", "").split(";")[0].strip() == "application/json":
            return UserLogin.model_validate(await request.json())
        form = await request.form()
        oauth = OAuth2PasswordRequestForm(username=form.get("username", ""),
                                        password=form.get("password", ""))
        return UserLogin(email=oauth.username, password=oauth.password)
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            errors = [{"loc": ("body", *e["loc"]), "msg": e["msg"], "type": e["type"]}
                      for e in error.errors()]
        else:
            errors = [{"loc": ("body",), "msg": "Cuerpo inválido", "type": "value_error"}]
        raise RequestValidationError(errors) from None


@auth_router.post("/register", response_model=UserResponse, status_code=201,
                  summary="Registrar cuenta", description="Crea una cuenta con contraseña segura y correo único.")
@limiter.limit("3/minute")
def register(request: Request, data: UserRegister, db: DatabaseSession):
    return auth_service.register_user(db, data)


@auth_router.post("/login", response_model=Token, summary="Iniciar sesión",
                  description="OAuth2: username contiene el correo. También acepta JSON email/password.",
                  openapi_extra={"requestBody": {"required": True, "content": {
                      "application/x-www-form-urlencoded": {"schema": {"type": "object",
                          "required": ["username", "password"], "properties": {
                              "username": {"type": "string", "format": "email"},
                              "password": {"type": "string", "format": "password"}}}},
                      "application/json": {"schema": UserLogin.model_json_schema()}}}})
@limiter.limit("5/minute")
def login(request: Request, db: DatabaseSession, data: Annotated[UserLogin, Depends(login_payload)]):
    return auth_service.login_user(db, data)


@auth_router.get("/me", response_model=UserResponse, summary="Consultar mi cuenta",
                 description="Devuelve el usuario activo autenticado, sin credenciales.")
def me(user: CurrentActiveUser):
    return user
