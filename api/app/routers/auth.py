from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models.orm import Usuario
from app.models.schemas import LoginRequest, LoginResponse, UsuarioPublic
from app.services.auth import authenticate, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _cookie_max_age() -> int:
    return max(1, settings.jwt_expire_days) * 24 * 60 * 60


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=_cookie_max_age(),
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.auth_cookie_name, path="/")


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    usuario = authenticate(db, body.email, body.senha)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos")
    token = create_access_token(usuario.id)
    _set_auth_cookie(response, token)
    return LoginResponse(
        access_token=token,
        usuario=UsuarioPublic(id=usuario.id, email=usuario.email, nome=usuario.nome),
    )


@router.get("/me", response_model=UsuarioPublic)
def me(usuario: Usuario = Depends(get_current_user)) -> UsuarioPublic:
    return UsuarioPublic(id=usuario.id, email=usuario.email, nome=usuario.nome)


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    _clear_auth_cookie(response)
    return {"status": "ok"}
