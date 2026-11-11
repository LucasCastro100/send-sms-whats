"""Senhas (bcrypt) e tokens (JWT)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from .config import settings

ALGORITHM = "HS256"


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def criar_token(usuario: str) -> str:
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": usuario,
        "iat": agora,
        "exp": agora + timedelta(hours=settings.token_horas),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def ler_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None
