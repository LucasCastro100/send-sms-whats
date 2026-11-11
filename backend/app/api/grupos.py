"""Grupos de assistência do ICM."""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..db import get_session
from ..deps import admin_atual, usuario_atual
from ..models import GrupoAssistencia, User
from ..services import grupos as servico_grupos

router = APIRouter(prefix="/api/grupos-assistencia", tags=["grupos"])


class GrupoOut(BaseModel):
    id: int
    nome: str
    responsavel_nome: str = ""
    responsavel_whatsapp: str = ""


class GrupoPatch(BaseModel):
    responsavel_nome: Optional[str] = Field(default=None, max_length=160)
    responsavel_whatsapp: Optional[str] = Field(default=None, max_length=20)


def _whatsapp(valor: object) -> str:
    digitos = re.sub(r"\D", "", str(valor or ""))
    if not digitos:
        return ""
    if not (10 <= len(digitos) <= 15):
        raise HTTPException(
            status_code=400,
            detail="WhatsApp do responsável incompleto. Use DDI + DDD + número.",
        )
    return digitos


def _saida(grupo) -> GrupoOut:  # noqa: ANN001
    return GrupoOut(
        id=int(grupo.id or 0),
        nome=grupo.nome,
        responsavel_nome=grupo.responsavel_nome,
        responsavel_whatsapp=grupo.responsavel_whatsapp,
    )


@router.get("", response_model=list[GrupoOut])
def listar(
    session: Session = Depends(get_session),
    _: User = Depends(usuario_atual),
) -> list[GrupoOut]:
    return [_saida(grupo) for grupo in servico_grupos.listar(session)]


@router.patch("/{grupo_id}", response_model=GrupoOut)
def editar(
    grupo_id: int,
    dados: GrupoPatch,
    session: Session = Depends(get_session),
    _: User = Depends(admin_atual),
) -> GrupoOut:
    grupo = session.get(GrupoAssistencia, grupo_id)
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo não encontrado.")

    nome = grupo.responsavel_nome
    whatsapp = grupo.responsavel_whatsapp
    if "responsavel_nome" in dados.model_fields_set:
        nome = (dados.responsavel_nome or "").strip()
    if "responsavel_whatsapp" in dados.model_fields_set:
        whatsapp = _whatsapp(dados.responsavel_whatsapp)

    atualizado = servico_grupos.atualizar_responsavel(
        session, grupo_id, nome, whatsapp
    )
    return _saida(atualizado)
