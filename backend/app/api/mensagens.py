"""Envio avulso de mensagens e agendamentos."""

from __future__ import annotations

import re
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..deps import usuario_atual
from ..models import Agendamento, Disparo, User
from ..services import disparo_automatico, evolution, horarios
from ..services import mensagens as servico_mensagens

router = APIRouter(prefix="/api/mensagens", tags=["mensagens"])

LIMITE_TEXTO = 4000


class Destino(BaseModel):
    jid: str
    nome: str = ""


class Envio(BaseModel):
    texto: str
    destinos: List[Destino]


class AgendamentoEntrada(Envio):
    # ISO 8601 em UTC (o que o `toISOString()` do navegador devolve).
    quando: str


# ---------------------------------------------------------------------------
# Validação e saída
# ---------------------------------------------------------------------------
def _limpar_destino(jid: str) -> str:
    alvo = (jid or "").strip()
    if alvo.endswith("@g.us"):
        return alvo
    return re.sub(r"\D", "", alvo)


def _validar(dados: Envio) -> tuple:
    texto = (dados.texto or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Escreva o texto da mensagem.")
    if len(texto) > LIMITE_TEXTO:
        raise HTTPException(
            status_code=400,
            detail=f"Mensagem muito longa (máximo {LIMITE_TEXTO} caracteres).",
        )
    if not dados.destinos:
        raise HTTPException(status_code=400, detail="Escolha pelo menos um destino.")

    destinos: list = []
    for destino in dados.destinos:
        jid = _limpar_destino(destino.jid)
        if not jid:
            raise HTTPException(status_code=400, detail="Destino inválido.")
        if not jid.endswith("@g.us") and not (10 <= len(jid) <= 15):
            raise HTTPException(
                status_code=400,
                detail=f"Número inválido: {destino.jid}. Use DDI + DDD + número.",
            )
        nome = (destino.nome or "").strip() or evolution.formatar_numero(jid)
        destinos.append({"jid": jid, "nome": nome})

    return texto, destinos


def _saida(item: Agendamento) -> dict:
    return {
        "id": int(item.id or 0),
        "texto": item.texto,
        "destino": item.destino,
        "nome": item.nome,
        "quando": horarios.formatar(item.quando),
        "quando_iso": item.quando.isoformat() + "Z",
        "status": item.status,
        "resultado": item.resultado,
        "criado_em": horarios.formatar(item.criado_em),
        "executado_em": horarios.formatar(item.executado_em),
    }


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
@router.post("/enviar")
def enviar(dados: Envio, user: User = Depends(usuario_atual)) -> dict:
    texto, destinos = _validar(dados)

    resultados = []
    for destino in destinos:
        ok, retorno = evolution.enviar_texto(user.instancia, destino["jid"], texto)
        resultados.append(
            {
                "nome": destino["nome"],
                "jid": destino["jid"],
                "ok": ok,
                "mensagem": retorno,
            }
        )

    enviados = sum(1 for item in resultados if item["ok"])
    return {
        "enviados": enviados,
        "falhas": len(resultados) - enviados,
        "resultados": resultados,
    }


@router.post("/agendar")
def agendar(
    dados: AgendamentoEntrada,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    texto, destinos = _validar(dados)

    quando = horarios.de_iso(dados.quando)
    if quando is None:
        raise HTTPException(status_code=400, detail="Data/hora inválida.")
    if quando <= datetime.utcnow():
        raise HTTPException(
            status_code=400, detail="Escolha um horário no futuro."
        )

    criados = []
    for destino in destinos:
        item = Agendamento(
            texto=texto,
            destino=destino["jid"],
            nome=destino["nome"],
            quando=quando,
            instancia=user.instancia,
            usuario_id=user.id,
            usuario=user.usuario,
        )
        session.add(item)
        criados.append(item)

    session.commit()
    for item in criados:
        session.refresh(item)

    return {
        "total": len(criados),
        "agendamentos": [_saida(item) for item in criados],
    }


@router.get("/agendamentos")
def agendamentos(
    limite: int = 50,
    session: Session = Depends(get_session),
    _: User = Depends(usuario_atual),
) -> dict:
    limite = max(1, min(limite, 200))

    pendentes = session.exec(
        select(Agendamento)
        .where(Agendamento.status == "pendente")
        .order_by(Agendamento.quando)
    ).all()

    historico = session.exec(
        select(Agendamento)
        .where(Agendamento.status != "pendente")
        .order_by(Agendamento.quando.desc())
        .limit(limite)
    ).all()

    return {
        "pendentes": [_saida(item) for item in pendentes],
        "historico": [_saida(item) for item in historico],
    }


@router.delete("/agendamentos/{agendamento_id}")
def cancelar(
    agendamento_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(usuario_atual),
) -> dict:
    item = session.get(Agendamento, agendamento_id)
    if not item:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")
    if item.status != "pendente":
        raise HTTPException(
            status_code=400,
            detail="Esse agendamento já foi processado e não pode ser cancelado.",
        )

    item.status = "cancelado"
    session.add(item)
    session.commit()
    return {"ok": True, "id": agendamento_id}


@router.get("/automatico")
def automatico(
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    consulta = select(Disparo)
    if not user.admin:
        # O histórico do Zoom é restrito ao administrador.
        consulta = consulta.where(Disparo.fonte != "zoom")
    ultimos = session.exec(
        consulta.order_by(Disparo.data.desc()).limit(10)
    ).all()

    destino = servico_mensagens.destino(settings.disparo_fonte)

    return {
        "ativo": settings.disparo_automatico,
        "hora": settings.disparo_hora,
        "minuto": settings.disparo_minuto,
        "fonte": settings.disparo_fonte,
        "instancia": settings.evolution_instance,
        "destino": destino,
        "ultimos": [
            {
                "id": int(item.id or 0),
                "data": item.data,
                "fonte": item.fonte,
                "destino": item.destino,
                "nome": item.nome,
                "citados": item.citados,
                "status": item.status,
                "resultado": item.resultado,
                "executado_em": horarios.formatar(item.executado_em),
            }
            for item in ultimos
        ],
    }


@router.post("/automatico/disparar")
def disparar_agora(_: User = Depends(usuario_atual)) -> dict:
    resultado = disparo_automatico.processar(forcar=True)
    if resultado.get("status") == "erro":
        raise HTTPException(
            status_code=400,
            detail=resultado.get("resultado") or resultado.get("motivo"),
        )
    return resultado
