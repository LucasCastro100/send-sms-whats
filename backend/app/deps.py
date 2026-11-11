"""Dependências do FastAPI: usuário logado e admin."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, select

from .config import settings
from .db import get_session
from .models import User
from .security import ler_token


def _token_da_requisicao(request: Request) -> Optional[str]:
    token = request.cookies.get(settings.cookie_name)
    if token:
        return token

    autorizacao = request.headers.get("authorization", "")
    if autorizacao.lower().startswith("bearer "):
        return autorizacao[7:].strip()
    return None


def usuario_atual(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    token = _token_da_requisicao(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado.",
        )

    usuario = ler_token(token)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada.",
        )

    user = session.exec(select(User).where(User.usuario == usuario)).first()
    if not user or not user.ativo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário inativo.",
        )
    return user


def admin_atual(user: User = Depends(usuario_atual)) -> User:
    if not user.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores.",
        )
    return user
