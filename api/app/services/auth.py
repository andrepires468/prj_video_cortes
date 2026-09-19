from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models.orm import Usuario

_bearer = HTTPBearer(auto_error=False)


def create_access_token(usuario_id: str) -> str:
    secret = (settings.jwt_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET não configurado")
    expire = datetime.now(timezone.utc) + timedelta(days=max(1, settings.jwt_expire_days))
    payload = {"sub": usuario_id, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str) -> str:
    secret = (settings.jwt_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET não configurado")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão expirada") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado") from exc
    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")
    return sub


def verify_password(plain: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), senha_hash.encode("utf-8"))
    except ValueError:
        return False


def authenticate(db: Session, email: str, senha: str) -> Usuario | None:
    normalized = email.strip().lower()
    usuario = (
        db.query(Usuario)
        .filter(func.lower(Usuario.email) == normalized)
        .one_or_none()
    )
    if not usuario or not verify_password(senha, usuario.senha_hash):
        return None
    return usuario


def _token_from_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    if credentials and credentials.scheme.lower() == "bearer" and credentials.credentials:
        return credentials.credentials
    cookie = request.cookies.get(settings.auth_cookie_name)
    if cookie:
        return cookie
    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Usuario:
    token = _token_from_request(request, credentials)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")
    usuario_id = decode_access_token(token)
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")
    return usuario
