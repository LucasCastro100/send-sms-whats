"""Rotas de autenticação: login, logout e usuário atual."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..deps import usuario_atual
from ..models import User
from ..security import criar_token, verificar_senha
from ..services import grupos as servico_grupos

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    usuario: str = Field(min_length=1, max_length=120)
    senha: str = Field(min_length=1, max_length=128)


class UsuarioOut(BaseModel):
    id: int
    nome: str
    usuario: str
    admin: bool
    funcao: str
    ativo: bool
    instancia: str
    grupo_id: Optional[int] = None
    grupo_nome: str = ""


def _saida(user: User, session: Session) -> UsuarioOut:
    return UsuarioOut(
        id=int(user.id or 0),
        nome=user.nome,
        usuario=user.usuario,
        admin=user.admin,
        funcao=servico_grupos.funcao_do_usuario(user),
        ativo=user.ativo,
        instancia=user.instancia,
        grupo_id=user.grupo_id,
        grupo_nome=servico_grupos.nome_do_usuario(session, user),
    )


def _logar(response: Response, user: User) -> None:
    samesite = settings.cookie_samesite.strip().lower()
    if samesite not in ("lax", "strict", "none"):
        samesite = "lax"
    response.set_cookie(
        key=settings.cookie_name,
        value=criar_token(user.usuario),
        httponly=True,
        samesite=samesite,  # type: ignore[arg-type]
        secure=settings.cookie_secure,
        max_age=settings.token_horas * 3600,
        path="/",
    )


@router.post("/login", response_model=UsuarioOut)
def login(
    dados: LoginIn,
    response: Response,
    session: Session = Depends(get_session),
) -> UsuarioOut:
    usuario = dados.usuario.strip().lower()
    user = session.exec(select(User).where(User.usuario == usuario)).first()

    if not user or not verificar_senha(dados.senha, user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos.",
        )
    if not user.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário desativado.",
        )

    _logar(response, user)
    return _saida(user, session)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(settings.cookie_name, path="/")
    return {"ok": True}


@router.get("/me", response_model=UsuarioOut)
def me(
    user: User = Depends(usuario_atual),
    session: Session = Depends(get_session),
) -> UsuarioOut:
    return _saida(user, session)
