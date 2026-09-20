"""Configuración de la API y JWT desde el entorno o .env local."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

APP_NAME = os.getenv("APP_NAME") or "device_systems"
APP_VERSION = "3.0.0"
ADMIN_USER = os.getenv("ADMIN_USER") or "admin"
SECRET_KEY = os.getenv("SECRET_KEY", "")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))


def validate_security_settings():
    if len(SECRET_KEY.encode()) < 32:
        raise RuntimeError("Configure SECRET_KEY con al menos 32 bytes aleatorios en .env")
    if ALGORITHM not in {"HS256", "HS384", "HS512"}:
        raise RuntimeError("ALGORITHM debe ser HS256, HS384 o HS512")
    if ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES debe ser positivo")
