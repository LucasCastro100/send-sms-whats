"""Motivos de oração lançados na ficha das vidas do ICM."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..deps import usuario_atual
from ..models import MotivoOracao, PessoaICM, User
from ..services import grupos as servico_grupos
from ..services import igrejas as servico_igrejas
from ..services import pessoas as servico_pessoas

router = APIRouter(prefix="/api/oracoes", tags=["oracoes"])

STATUS = ("aberto", "atendido")


class OracaoOut(BaseModel):
    id: int
    pessoa_id: int
    nome: str
    nome_chave: str
    texto: str
    status: str
    criado_por: str
    criado_em: str
    atendido_em: Optional[str]
    grupo: str
    igreja_id: Optional[int]
    igreja_nome: str


class OracaoIn(BaseModel):
    pessoa_id: int
    fonte: str = "icm"
    texto: str = Field(min_length=2, max_length=1000)


class OracaoPatch(BaseModel):
    texto: Optional[str] = Field(default=None, min_length=2, max_length=1000)
    status: Optional[str] = None


def _chaves_do_escopo(session: Session, user: User) -> set[str]:
    escopo = servico_grupos.escopo(session, user)
    pessoas = servico_pessoas.listar(
        session,
        fonte="icm",
        grupos=escopo["grupos"],
        apenas_mulheres=escopo["apenas_mulheres"],
    )
    return {pessoa.nome_chave for pessoa in pessoas}


def _pessoa_do_escopo(
    session: Session, user: User, pessoa_id: int, fonte: str
) -> PessoaICM:
    if (fonte or "icm").lower() != "icm":
        raise HTTPException(
            status_code=400,
            detail="Os motivos de oração valem apenas para a lista ICM.",
        )
    pessoa = session.get(PessoaICM, pessoa_id)
    if not pessoa:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada.")
    if pessoa.nome_chave not in _chaves_do_escopo(session, user):
        raise HTTPException(
            status_code=403, detail="Você não tem acesso a esta vida."
        )
    return pessoa


def _saida(
    session: Session, motivo: MotivoOracao, igrejas: dict[int, str]
) -> OracaoOut:
    pessoa = session.exec(
        select(PessoaICM).where(PessoaICM.nome_chave == motivo.nome_chave)
    ).first()
    igreja_id = getattr(pessoa, "igreja_id", None) if pessoa else None
    return OracaoOut(
        id=int(motivo.id or 0),
        pessoa_id=int(pessoa.id or 0) if pessoa else 0,
        nome=motivo.nome or (pessoa.nome if pessoa else motivo.nome_chave),
        nome_chave=motivo.nome_chave,
        texto=motivo.texto,
        status=motivo.status,
        criado_por=motivo.criado_por,
        criado_em=motivo.criado_em.strftime("%d/%m/%Y %H:%M"),
        atendido_em=(
            motivo.atendido_em.strftime("%d/%m/%Y %H:%M")
            if motivo.atendido_em
            else None
        ),
        grupo=pessoa.grupo if pessoa else "",
        igreja_id=igreja_id,
        igreja_nome=igrejas.get(igreja_id, "") if igreja_id else "",
    )


@router.get("", response_model=list[OracaoOut])
def listar(
    pessoa_id: Optional[int] = None,
    fonte: str = "icm",
    status: Optional[str] = None,
    busca: Optional[str] = None,
    grupo: Optional[str] = None,
    igreja_id: Optional[int] = None,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> list[OracaoOut]:
    chaves = _chaves_do_escopo(session, user)
    if not chaves:
        return []

    consulta = select(MotivoOracao).where(
        MotivoOracao.nome_chave.in_(sorted(chaves))  # type: ignore[attr-defined]
    )

    if pessoa_id:
        pessoa = _pessoa_do_escopo(session, user, pessoa_id, fonte)
        consulta = consulta.where(MotivoOracao.nome_chave == pessoa.nome_chave)

    if status and status.lower() != "todos":
        if status.lower() not in STATUS:
            raise HTTPException(
                status_code=400, detail="Status deve ser `aberto` ou `atendido`."
            )
        consulta = consulta.where(MotivoOracao.status == status.lower())

    if busca and busca.strip():
        termo = f"%{servico_pessoas.normalizar_nome(busca)}%"
        consulta = consulta.where(MotivoOracao.nome_chave.like(termo))

    motivos = list(
        session.exec(
            consulta.order_by(
                MotivoOracao.status.desc(), MotivoOracao.criado_em.desc()
            )
        ).all()
    )

    igrejas = servico_igrejas.mapa(session)
    saida = [_saida(session, motivo, igrejas) for motivo in motivos]

    if grupo:
        saida = [item for item in saida if item.grupo == grupo]
    if igreja_id:
        saida = [item for item in saida if item.igreja_id == igreja_id]
    return saida


@router.post("", response_model=OracaoOut, status_code=201)
def criar(
    dados: OracaoIn,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> OracaoOut:
    pessoa = _pessoa_do_escopo(session, user, dados.pessoa_id, dados.fonte)
    motivo = MotivoOracao(
        nome=pessoa.nome,
        nome_chave=pessoa.nome_chave,
        texto=dados.texto.strip(),
        status="aberto",
        criado_por=user.nome,
    )
    session.add(motivo)
    session.commit()
    session.refresh(motivo)
    return _saida(session, motivo, servico_igrejas.mapa(session))


@router.patch("/{motivo_id}", response_model=OracaoOut)
def editar(
    motivo_id: int,
    dados: OracaoPatch,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> OracaoOut:
    motivo = session.get(MotivoOracao, motivo_id)
    if not motivo:
        raise HTTPException(status_code=404, detail="Motivo não encontrado.")
    if motivo.nome_chave not in _chaves_do_escopo(session, user):
        raise HTTPException(
            status_code=403, detail="Você não tem acesso a esta vida."
        )

    if dados.texto is not None:
        motivo.texto = dados.texto.strip()

    if dados.status is not None:
        novo = dados.status.strip().lower()
        if novo not in STATUS:
            raise HTTPException(
                status_code=400, detail="Status deve ser `aberto` ou `atendido`."
            )
        if novo == "atendido" and motivo.status != "atendido":
            motivo.atendido_em = datetime.utcnow()
        if novo == "aberto":
            motivo.atendido_em = None
        motivo.status = novo

    motivo.atualizado_em = datetime.utcnow()
    session.add(motivo)
    session.commit()
    session.refresh(motivo)
    return _saida(session, motivo, servico_igrejas.mapa(session))


@router.delete("/{motivo_id}")
def excluir(
    motivo_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    motivo = session.get(MotivoOracao, motivo_id)
    if not motivo:
        raise HTTPException(status_code=404, detail="Motivo não encontrado.")
    if motivo.nome_chave not in _chaves_do_escopo(session, user):
        raise HTTPException(
            status_code=403, detail="Você não tem acesso a esta vida."
        )

    session.delete(motivo)
    session.commit()
    return {"ok": True}
