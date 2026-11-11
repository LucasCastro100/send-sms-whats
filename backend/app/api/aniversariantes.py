"""Aniversariantes do dia, mensagem pronta e disparo para o grupo."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from ..db import get_session
from ..deps import usuario_atual
from ..models import User
from ..services import evolution
from ..services import grupos as servico_grupos
from ..services import igrejas as servico_igrejas
from ..services import mensagens as servico_mensagens
from ..services import pessoas as servico_pessoas
from .pessoas import saida

router = APIRouter(prefix="/api/aniversariantes", tags=["aniversariantes"])


class Disparo(BaseModel):
    fonte: str
    dia: int
    mes: int


def _validar_fonte(fonte: str, user: User) -> str:
    fonte = (fonte or "").strip().lower()
    if fonte not in servico_pessoas.FONTES:
        raise HTTPException(status_code=400, detail="Fonte inválida.")
    if fonte not in servico_pessoas.fontes_do_usuario(user):
        raise HTTPException(
            status_code=403,
            detail="A lista do Zoom é restrita ao administrador.",
        )
    return fonte


def _validar_data(dia: int, mes: int) -> None:
    if not (1 <= dia <= 31 and 1 <= mes <= 12):
        raise HTTPException(status_code=400, detail="Data inválida.")


@router.get("/dia")
def dia(
    fonte: str = "icm",
    dia: int = 1,
    mes: int = 1,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    fonte = _validar_fonte(fonte, user)
    _validar_data(dia, mes)

    escopo = servico_grupos.escopo(session, user)
    igrejas = servico_igrejas.mapa(session)
    todos = servico_pessoas.listar(
        session,
        fonte=fonte,
        grupos=escopo["grupos"],
        apenas_mulheres=escopo["apenas_mulheres"],
    )
    do_dia = servico_mensagens.da_data(todos, dia, mes)
    citados = [pessoa for pessoa in do_dia if not pessoa.excluido]

    data_str = servico_pessoas.formatar_data(dia, mes)
    destino = servico_mensagens.destino(fonte)

    return {
        "fonte": fonte,
        "dia": dia,
        "mes": mes,
        "data": data_str,
        "mes_nome": servico_pessoas.nome_mes(mes),
        "destino": destino,
        "pessoas": [saida(pessoa, igrejas) for pessoa in do_dia],
        "citados": len(citados),
        "nao_citados": len(do_dia) - len(citados),
        "mensagem": servico_mensagens.montar(citados, fonte, data_str),
    }


@router.post("/enviar")
def enviar(
    dados: Disparo,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    fonte = _validar_fonte(dados.fonte, user)
    _validar_data(dados.dia, dados.mes)

    destino = servico_mensagens.destino(fonte)
    if not destino["jid"]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Grupo do {destino['nome']} não configurado. Defina "
                "`JID_GRUPO_ZOOM` no `.env`."
            ),
        )

    todos = servico_pessoas.listar(session, fonte=fonte)
    citados = servico_mensagens.do_dia(todos, dados.dia, dados.mes)
    if not citados:
        raise HTTPException(
            status_code=400,
            detail="Nenhum aniversariante para citar nesta data.",
        )

    data_str = servico_pessoas.formatar_data(dados.dia, dados.mes)
    texto = servico_mensagens.montar(citados, fonte, data_str)

    sucesso, retorno = evolution.enviar_texto(user.instancia, destino["jid"], texto)
    if not sucesso:
        raise HTTPException(status_code=400, detail=retorno)

    return {
        "ok": True,
        "grupo": destino["nome"],
        "citados": len(citados),
        "mensagem": texto,
    }
