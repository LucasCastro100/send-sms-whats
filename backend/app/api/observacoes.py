"""Observações (anotações) da ficha de uma vida do ICM."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..deps import usuario_atual
from ..models import Observacao, PessoaICM, User
from ..services import grupos as servico_grupos

router = APIRouter(prefix="/api/observacoes", tags=["observacoes"])


class ObservacaoOut(BaseModel):
    id: int
    pessoa_id: int
    nome: str
    nome_chave: str
    texto: str
    criado_por: str
    criado_em: str


class ObservacaoIn(BaseModel):
    pessoa_id: int
    fonte: str = "icm"
    texto: str = Field(min_length=2, max_length=2000)


class ObservacaoPatch(BaseModel):
    texto: str = Field(min_length=2, max_length=2000)


def _pessoa_do_escopo(
    session: Session, user: User, pessoa_id: int, fonte: str
) -> PessoaICM:
    if (fonte or "icm").lower() != "icm":
        raise HTTPException(
            status_code=400,
            detail="As observações valem apenas para a lista ICM.",
        )
    pessoa = session.get(PessoaICM, pessoa_id)
    if not pessoa:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada.")
    if pessoa.nome_chave not in servico_grupos.chaves_do_escopo(session, user):
        raise HTTPException(
            status_code=403, detail="Você não tem acesso a esta vida."
        )
    return pessoa


def _pessoa_da_observacao(session: Session, observacao: Observacao) -> PessoaICM:
    pessoa = session.exec(
        select(PessoaICM).where(PessoaICM.nome_chave == observacao.nome_chave)
    ).first()
    if not pessoa:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada.")
    return pessoa


def _saida(pessoa: PessoaICM, observacao: Observacao) -> ObservacaoOut:
    return ObservacaoOut(
        id=int(observacao.id or 0),
        pessoa_id=int(pessoa.id or 0),
        nome=observacao.nome or pessoa.nome,
        nome_chave=observacao.nome_chave,
        texto=observacao.texto,
        criado_por=observacao.criado_por,
        criado_em=observacao.criado_em.strftime("%d/%m/%Y %H:%M"),
    )


@router.get("", response_model=list[ObservacaoOut])
def listar(
    pessoa_id: int,
    fonte: str = "icm",
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> list[ObservacaoOut]:
    pessoa = _pessoa_do_escopo(session, user, pessoa_id, fonte)
    observacoes = session.exec(
        select(Observacao)
        .where(Observacao.nome_chave == pessoa.nome_chave)
        .order_by(Observacao.criado_em.desc())
    ).all()
    return [_saida(pessoa, item) for item in observacoes]


@router.post("", response_model=ObservacaoOut, status_code=201)
def criar(
    dados: ObservacaoIn,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> ObservacaoOut:
    pessoa = _pessoa_do_escopo(session, user, dados.pessoa_id, dados.fonte)
    observacao = Observacao(
        nome=pessoa.nome,
        nome_chave=pessoa.nome_chave,
        texto=dados.texto.strip(),
        criado_por=user.nome,
    )
    session.add(observacao)
    session.commit()
    session.refresh(observacao)
    return _saida(pessoa, observacao)


@router.patch("/{observacao_id}", response_model=ObservacaoOut)
def editar(
    observacao_id: int,
    dados: ObservacaoPatch,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> ObservacaoOut:
    observacao = session.get(Observacao, observacao_id)
    if not observacao:
        raise HTTPException(status_code=404, detail="Observação não encontrada.")
    pessoa = _pessoa_da_observacao(session, observacao)
    if pessoa.nome_chave not in servico_grupos.chaves_do_escopo(session, user):
        raise HTTPException(
            status_code=403, detail="Você não tem acesso a esta vida."
        )

    observacao.texto = dados.texto.strip()
    observacao.atualizado_em = datetime.utcnow()
    session.add(observacao)
    session.commit()
    session.refresh(observacao)
    return _saida(pessoa, observacao)


@router.delete("/{observacao_id}")
def excluir(
    observacao_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    observacao = session.get(Observacao, observacao_id)
    if not observacao:
        raise HTTPException(status_code=404, detail="Observação não encontrada.")
    pessoa = _pessoa_da_observacao(session, observacao)
    if pessoa.nome_chave not in servico_grupos.chaves_do_escopo(session, user):
        raise HTTPException(
            status_code=403, detail="Você não tem acesso a esta vida."
        )

    session.delete(observacao)
    session.commit()
    return {"ok": True}
