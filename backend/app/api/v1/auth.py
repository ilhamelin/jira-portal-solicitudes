from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from ...core.security import create_access_token, dummy_password_hash, verify_password
from ...models import Usuario
from ...schemas.auth import LoginRequest, TokenResponse, UserResponse
from ..deps import AuthenticatedUser, Database

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: Database) -> TokenResponse:
    user = await db.scalar(select(Usuario).where(Usuario.email == str(payload.email)))
    password_hash = user.password_hash if user else await run_in_threadpool(dummy_password_hash)
    valid = await run_in_threadpool(verify_password, payload.password, password_hash)
    if not user or not valid:
        raise HTTPException(
            status_code=401, detail="Email o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(
        access_token=create_access_token(user.id, user.rol, request.app.state.settings),
        user_id=user.id, rol=user.rol, nombre=user.nombre,
    )


@router.get("/me", response_model=UserResponse)
async def me(user: AuthenticatedUser) -> Usuario:
    return user
