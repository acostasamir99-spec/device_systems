"""Hashes Passlib y tokens JWT firmados con expiración obligatoria."""
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

# bcrypt_sha256 evita el truncamiento de bcrypt a 72 bytes, también con Unicode.
password_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return password_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return password_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        return False


def generate_unusable_password_hash() -> str:
    """Compatibilidad: contraseña aleatoria que nunca se guarda ni se devuelve."""
    return get_password_hash(token_urlsafe(48))


def create_access_token(data: dict) -> str:
    settings.validate_security_settings()
    payload = data.copy()
    now = datetime.now(timezone.utc)
    payload.update(iat=now, exp=now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    settings.validate_security_settings()
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
                      options={"require_exp": True, "require_sub": True})
