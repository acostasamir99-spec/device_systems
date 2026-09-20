"""Configuración aislada de seguridad para todas las pruebas."""
import secrets

import pytest

from app.config import settings
from app.middlewares.request_middleware import limiter


@pytest.fixture(autouse=True)
def isolate_security(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", secrets.token_urlsafe(48))
    monkeypatch.setattr(settings, "ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    limiter.reset()
    yield
    limiter.reset()
