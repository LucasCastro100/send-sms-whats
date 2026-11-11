"""Resumo do painel inicial."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from ..db import get_session
from ..deps import usuario_atual
from ..models import User
from ..services import evolution

router = APIRouter(prefix="/api", tags=["painel"])


@router.get("/resumo")
def resumo(
    user: User = Depends(usuario_atual),
    session: Session = Depends(get_session),
) -> dict:
    status = evolution.resumo_instancias().get(user.instancia) or {}
    estado = status.get("estado") or evolution.estado(user.instancia)

    saida = {
        "usuario": {
            "nome": user.nome,
            "usuario": user.usuario,
            "admin": user.admin,
        },
        "whatsapp": {
            "instancia": user.instancia,
            "estado": estado,
            "perfil": status.get("perfil", ""),
            "numero": status.get("numero", ""),
        },
    }

    # A contagem de usuários só interessa (e só é visível) para o admin.
    if user.admin:
        total_usuarios = session.exec(select(func.count()).select_from(User)).one()
        ativos = session.exec(
            select(func.count())
            .select_from(User)
            .where(User.ativo == True)  # noqa: E712
        ).one()
        saida["usuarios"] = {"total": int(total_usuarios), "ativos": int(ativos)}

    return saida
