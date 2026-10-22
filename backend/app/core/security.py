from datetime import datetime, timedelta, timezone
from functools import lru_cache
from uuid import UUID

from jose import jwt
from passlib.context import CryptContext

from .config import Settings

ALGORITHM = "HS256"
ACCESS_TOKEN_HOURS = 8
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("bcrypt admite hasta 72 bytes por contraseña.")
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if len(password.encode("utf-8")) > 72:
        return False
    try:
        return password_context.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


@lru_cache
def dummy_password_hash() -> str:
    return get_password_hash("Verificacion de usuario inexistente")


def create_access_token(subject: UUID | str, rol: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(subject), "rol": rol, "iat": now,
         "exp": now + timedelta(hours=ACCESS_TOKEN_HOURS)},
        settings.jwt_secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )
