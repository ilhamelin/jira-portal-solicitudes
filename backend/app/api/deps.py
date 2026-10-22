from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import ALGORITHM
from ..models import Usuario
from ..services.jira_client import JiraClient

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
Database = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(request: Request, db: Database, token: Annotated[str, Depends(oauth2_scheme)]) -> Usuario:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o sesión expirada.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, request.app.state.settings.jwt_secret_key.get_secret_value(),
            algorithms=[ALGORITHM], options={"require_exp": True, "require_sub": True},
        )
        user_id = UUID(payload["sub"])
    except (JWTError, ValueError, TypeError, KeyError):
        raise unauthorized from None
    user = await db.get(Usuario, user_id)
    if user is None:
        raise unauthorized
    # La autorización usa el rol vigente en la BD, no una declaración del cliente.
    return user


def require_role(*roles: str):
    async def check_role(user: Annotated[Usuario, Depends(get_current_user)]) -> Usuario:
        if user.rol not in roles:
            raise HTTPException(status_code=403, detail="No tienes permiso para esta operación.")
        return user
    return check_role


AuthenticatedUser = Annotated[Usuario, Depends(get_current_user)]
PortalUser = Annotated[Usuario, Depends(require_role("solicitante", "coordinador"))]


async def get_jira_client(request: Request) -> JiraClient:
    return request.app.state.jira_client
