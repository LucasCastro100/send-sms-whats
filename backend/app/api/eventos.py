"""Eventos da igreja (Maanaim, encontros, retiros...) e quem participou.

Cada evento tem a sua data (dois eventos nunca acontecem no mesmo dia) e a
vida do ICM pode participar de quantos eventos existirem.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..deps import admin_atual, usuario_atual
from ..models import Evento, EventoParticipante, PessoaICM, User
from ..services import grupos as servico_grupos

router = APIRouter(prefix="/api/eventos", tags=["eventos"])


class EventoOut(BaseModel):
    id: int
    nome: str
    data: str
    data_iso: str
    local: str
    descricao: str
    participantes: int
    criado_por: str
    criado_em: str
    participa: bool = False


class EventoIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    data: str
    local: str = Field(default="", max_length=160)
    descricao: str = Field(default="", max_length=1000)


class EventoPatch(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=2, max_length=120)
    data: Optional[str] = None
    local: Optional[str] = Field(default=None, max_length=160)
    descricao: Optional[str] = Field(default=None, max_length=1000)


class ParticipanteIn(BaseModel):
    pessoa_id: int
    fonte: str = "icm"


class ParticipanteOut(BaseModel):
    pessoa_id: int
    nome: str
    nome_chave: str


def _data(valor: str) -> date:
    try:
        return datetime.strptime(str(valor).strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400, detail="Data inválida. Use AAAA-MM-DD."
        )


def _data_br(valor: date) -> str:
    return valor.strftime("%d/%m/%Y")


def _pessoa_do_escopo(
    session: Session, user: User, pessoa_id: int, fonte: str
) -> PessoaICM:
    if (fonte or "icm").lower() != "icm":
        raise HTTPException(
            status_code=400,
            detail="Os eventos valem apenas para a lista ICM.",
        )
    pessoa = session.get(PessoaICM, pessoa_id)
    if not pessoa:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada.")
    if pessoa.nome_chave not in servico_grupos.chaves_do_escopo(session, user):
        raise HTTPException(
            status_code=403, detail="Você não tem acesso a esta vida."
        )
    return pessoa


def _participantes_por_evento(session: Session) -> dict[int, int]:
    contagem: dict[int, int] = {}
    for item in session.exec(select(EventoParticipante)).all():
        contagem[item.evento_id] = contagem.get(item.evento_id, 0) + 1
    return contagem


def _saida(
    evento: Evento,
    participantes: int,
    participa: bool = False,
) -> EventoOut:
    return EventoOut(
        id=int(evento.id or 0),
        nome=evento.nome,
        data=_data_br(evento.data),
        data_iso=evento.data.isoformat(),
        local=evento.local,
        descricao=evento.descricao,
        participantes=participantes,
        criado_por=evento.criado_por,
        criado_em=evento.criado_em.strftime("%d/%m/%Y %H:%M"),
        participa=participa,
    )


@router.get("", response_model=list[EventoOut])
def listar(
    pessoa_id: Optional[int] = None,
    fonte: str = "icm",
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> list[EventoOut]:
    pessoa = (
        _pessoa_do_escopo(session, user, pessoa_id, fonte)
        if pessoa_id
        else None
    )

    eventos = list(
        session.exec(select(Evento).order_by(Evento.data.desc())).all()
    )
    contagem = _participantes_por_evento(session)

    participacoes: set[int] = set()
    if pessoa:
        participacoes = {
            item.evento_id
            for item in session.exec(
                select(EventoParticipante).where(
                    EventoParticipante.nome_chave == pessoa.nome_chave
                )
            ).all()
        }

    return [
        _saida(
            evento,
            contagem.get(int(evento.id or 0), 0),
            int(evento.id or 0) in participacoes,
        )
        for evento in eventos
    ]


@router.post("", response_model=EventoOut, status_code=201)
def criar(
    dados: EventoIn,
    session: Session = Depends(get_session),
    user: User = Depends(admin_atual),
) -> EventoOut:
    evento = Evento(
        nome=dados.nome.strip(),
        data=_data(dados.data),
        local=dados.local.strip(),
        descricao=dados.descricao.strip(),
        criado_por=user.nome,
    )
    session.add(evento)
    session.commit()
    session.refresh(evento)
    return _saida(evento, 0)


@router.patch("/{evento_id}", response_model=EventoOut)
def editar(
    evento_id: int,
    dados: EventoPatch,
    session: Session = Depends(get_session),
    _: User = Depends(admin_atual),
) -> EventoOut:
    evento = session.get(Evento, evento_id)
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    if dados.nome is not None:
        evento.nome = dados.nome.strip()
    if dados.data is not None:
        evento.data = _data(dados.data)
    if dados.local is not None:
        evento.local = dados.local.strip()
    if dados.descricao is not None:
        evento.descricao = dados.descricao.strip()

    evento.atualizado_em = datetime.utcnow()
    session.add(evento)
    session.commit()
    session.refresh(evento)
    return _saida(evento, _participantes_por_evento(session).get(evento_id, 0))


@router.delete("/{evento_id}")
def excluir(
    evento_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(admin_atual),
) -> dict:
    evento = session.get(Evento, evento_id)
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    for item in session.exec(
        select(EventoParticipante).where(EventoParticipante.evento_id == evento_id)
    ).all():
        session.delete(item)
    session.delete(evento)
    session.commit()
    return {"ok": True}


@router.post("/{evento_id}/participantes", response_model=EventoOut)
def adicionar_participante(
    evento_id: int,
    dados: ParticipanteIn,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> EventoOut:
    evento = session.get(Evento, evento_id)
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    pessoa = _pessoa_do_escopo(session, user, dados.pessoa_id, dados.fonte)

    existente = session.exec(
        select(EventoParticipante).where(
            EventoParticipante.evento_id == evento_id,
            EventoParticipante.nome_chave == pessoa.nome_chave,
        )
    ).first()
    if not existente:
        session.add(
            EventoParticipante(
                evento_id=evento_id,
                nome=pessoa.nome,
                nome_chave=pessoa.nome_chave,
            )
        )
        session.commit()

    return _saida(evento, _participantes_por_evento(session).get(evento_id, 0), True)


@router.delete("/{evento_id}/participantes/{pessoa_id}")
def remover_participante(
    evento_id: int,
    pessoa_id: int,
    fonte: str = "icm",
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    evento = session.get(Evento, evento_id)
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    pessoa = _pessoa_do_escopo(session, user, pessoa_id, fonte)

    registro = session.exec(
        select(EventoParticipante).where(
            EventoParticipante.evento_id == evento_id,
            EventoParticipante.nome_chave == pessoa.nome_chave,
        )
    ).first()
    if registro:
        session.delete(registro)
        session.commit()
    return {"ok": True}


@router.get(
    "/{evento_id}/participantes", response_model=list[ParticipanteOut]
)
def listar_participantes(
    evento_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> list[ParticipanteOut]:
    evento = session.get(Evento, evento_id)
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    permitidas = servico_grupos.chaves_do_escopo(session, user)
    ids = {
        pessoa.nome_chave: int(pessoa.id or 0)
        for pessoa in session.exec(select(PessoaICM)).all()
    }

    registros = session.exec(
        select(EventoParticipante)
        .where(EventoParticipante.evento_id == evento_id)
        .order_by(EventoParticipante.nome)
    ).all()

    return [
        ParticipanteOut(
            pessoa_id=ids.get(item.nome_chave, 0),
            nome=item.nome or item.nome_chave,
            nome_chave=item.nome_chave,
        )
        for item in registros
        if item.nome_chave in permitidas
    ]
