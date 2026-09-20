from contextlib import asynccontextmanager #acciones
from app.database.connection import Base, engine
from app.models.user_model import User

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.auth.auth_routes import auth_router
from app.middlewares.request_middleware import RequestMiddleware, limiter

from app.config import settings
from app.routes.user_routes import user_router
from app.routes.device_routes import device_router
from app.routes.loan_routes import loan_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_security_settings()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="device_systems API",
    description="API REST segura para gestión de usuarios, dispositivos y préstamos",
    version=settings.APP_VERSION,
    contact={"name": "Samir Acosta Peña"},
    openapi_tags=[{"name": name} for name in ("Auth", "Users", "Devices", "Loans", "Security")],
)


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware,
                   allow_origins=["http://localhost:5173", "http://localhost:3000"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["X-Process-Time", "X-App-Name", "X-API-Version", "X-Request-ID"])
app.add_middleware(RequestMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, error: RequestValidationError):
    # Pydantic incluye input en sus errores: no devolver contraseñas ni hashes.
    errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in error.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.get("/", tags=["Security"], summary="Consultar información de la API",
         description="Muestra el nombre, la versión y el acceso a Swagger.",
         response_description="Información de device_systems")
def root():
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}


app.include_router(user_router)
app.include_router(device_router)
app.include_router(loan_router)

app.include_router(auth_router)
