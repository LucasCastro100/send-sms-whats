"""Cadastro de igrejas — criação, renomeação e exclusão são do admin."""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..deps import admin_atual, usuario_atual
from ..models import Igreja, User
from ..services import igrejas as servico_igrejas

router = APIRouter(prefix="/api/igrejas", tags=["igrejas"])


class IgrejaOut(BaseModel):
    id: int
    nome: str
    # Vidas da lista ICM vinculadas a esta igreja.
    total: int
    pastor_nome: str = ""
    pastor_whatsapp: str = ""


class IgrejaIn(BaseModel):
    nome: str = Field(min_length=2, max_length=160)
    pastor_nome: str = Field(default="", max_length=160)
    pastor_whatsapp: str = Field(default="", max_length=20)


class IgrejaPatch(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=2, max_length=160)
    pastor_nome: Optional[str] = Field(default=None, max_length=160)
    pastor_whatsapp: Optional[str] = Field(default=None, max_length=20)


def _busca_ou_404(session: Session, igreja_id: int) -> Igreja:
    igreja = session.get(Igreja, igreja_id)
    if not igreja:
        raise HTTPException(status_code=404, detail="Igreja não encontrada.")
    return igreja


def _whatsapp(valor: object) -> str:
    digitos = re.sub(r"\D", "", str(valor or ""))
    if not digitos:
        return ""
    if not (10 <= len(digitos) <= 15):
        raise HTTPException(
            status_code=400,
            detail="WhatsApp do pastor incompleto. Use DDI + DDD + número.",
        )
    return digitos


def _saida(session: Session, igreja: Igreja) -> IgrejaOut:
    igreja_id = int(igreja.id or 0)
    return IgrejaOut(
        id=igreja_id,
        nome=igreja.nome,
        total=servico_igrejas.total_vidas(session, igreja_id),
        pastor_nome=igreja.pastor_nome,
        pastor_whatsapp=igreja.pastor_whatsapp,
    )


@router.get("", response_model=list[IgrejaOut])
def listar(
    session: Session = Depends(get_session),
    _: User = Depends(usuario_atual),
) -> list[IgrejaOut]:
    return [_saida(session, igreja) for igreja in servico_igrejas.listar(session)]


@router.post("", response_model=IgrejaOut, status_code=201)
def criar(
    dados: IgrejaIn,
    session: Session = Depends(get_session),
    _: User = Depends(admin_atual),
) -> IgrejaOut:
    nome = dados.nome.strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome da igreja.")

    existente = session.exec(select(Igreja).where(Igreja.nome == nome)).first()
    if existente:
        raise HTTPException(
            status_code=409, detail="Já existe uma igreja com esse nome."
        )

    igreja = Igreja(
        nome=nome,
        pastor_nome=dados.pastor_nome.strip(),
        pastor_whatsapp=_whatsapp(dados.pastor_whatsapp),
    )
    session.add(igreja)
    session.commit()
    session.refresh(igreja)
    return _saida(session, igreja)


@router.patch("/{igreja_id}", response_model=IgrejaOut)
def editar(
    igreja_id: int,
    dados: IgrejaPatch,
    session: Session = Depends(get_session),
    _: User = Depends(admin_atual),
) -> IgrejaOut:
    igreja = _busca_ou_404(session, igreja_id)

    if "nome" in dados.model_fields_set and dados.nome is not None:
        nome = dados.nome.strip()
        if not nome:
            raise HTTPException(status_code=400, detail="Informe o nome da igreja.")

        conflito = session.exec(
            select(Igreja).where(Igreja.nome == nome, Igreja.id != igreja_id)
        ).first()
        if conflito:
            raise HTTPException(
                status_code=409, detail="Já existe uma igreja com esse nome."
            )
        igreja.nome = nome

    if "pastor_nome" in dados.model_fields_set:
        igreja.pastor_nome = (dados.pastor_nome or "").strip()
    if "pastor_whatsapp" in dados.model_fields_set:
        igreja.pastor_whatsapp = _whatsapp(dados.pastor_whatsapp)

    session.add(igreja)
    session.commit()
    session.refresh(igreja)
    return _saida(session, igreja)


@router.delete("/{igreja_id}")
def excluir(
    igreja_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(admin_atual),
) -> dict:
    igreja = _busca_ou_404(session, igreja_id)

    total = servico_igrejas.total_vidas(session, igreja_id)
    if total:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Existem {total} vida(s) vinculadas a esta igreja. "
                "Vincule-as a outra igreja antes de excluir."
            ),
        )

    session.delete(igreja)
    session.commit()
    return {"ok": True}
