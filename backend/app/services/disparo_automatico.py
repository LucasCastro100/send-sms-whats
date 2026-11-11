"""Disparo diário automático dos aniversariantes (conjunto ICM).

Uma thread daemon confere a cada minuto: passou do horário configurado
(`DISPARO_HORA`/`DISPARO_MINUTO`, horário de Brasília) e ainda não houve
disparo hoje? Então monta a mensagem a partir da tabela `icm` e envia pela
instância principal.

O registro na tabela `disparos` (único por dia e fonte) é o que impede o
mesmo dia de ser enviado duas vezes, inclusive depois de reiniciar o app.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime

from sqlmodel import Session, select

from ..config import settings
from ..db import engine
from ..models import Disparo
from . import evolution
from . import horarios
from . import mensagens as servico_mensagens
from . import pessoas as servico_pessoas

INTERVALO = 60  # segundos
_iniciado = False
_trava = threading.Lock()


def _registro_do_dia(session: Session, data: str, fonte: str) -> Disparo | None:
    return session.exec(
        select(Disparo).where(Disparo.data == data, Disparo.fonte == fonte)
    ).first()


def processar(forcar: bool = False) -> dict:
    """Faz o disparo do dia, se for a hora e ainda não tiver sido feito.

    `forcar=True` ignora o horário (usado pelo botão "Disparar agora"), mas
    continua respeitando o que já foi enviado hoje.
    """
    if not settings.disparo_automatico:
        return {
            "executado": False,
            "status": "desativado",
            "motivo": "disparo automático desativado",
        }

    agora = horarios.agora_brasilia()
    data = agora.strftime("%Y-%m-%d")
    fonte = settings.disparo_fonte

    if not forcar:
        alvo = agora.replace(
            hour=settings.disparo_hora,
            minute=settings.disparo_minuto,
            second=0,
            microsecond=0,
        )
        if agora < alvo:
            return {
                "executado": False,
                "status": "aguardando",
                "motivo": "antes do horário configurado",
            }

    with Session(engine) as session:
        registro = _registro_do_dia(session, data, fonte)
        if registro and registro.status in ("enviado", "vazio"):
            return {
                "executado": False,
                "status": registro.status,
                "motivo": f"já processado hoje ({registro.status})",
            }

        destino = servico_mensagens.destino(fonte)
        todos = servico_pessoas.listar(session, fonte=fonte)
        citados = servico_mensagens.do_dia(todos, agora.day, agora.month)

        if not citados:
            _salvar(
                session,
                registro,
                data=data,
                fonte=fonte,
                destino=destino["jid"],
                nome=destino["nome"],
                citados=0,
                status="vazio",
                resultado="Ninguém faz aniversário hoje.",
            )
            return {
                "executado": False,
                "status": "vazio",
                "motivo": "ninguém faz aniversário hoje",
            }

        if not destino["jid"]:
            _salvar(
                session,
                registro,
                data=data,
                fonte=fonte,
                destino="",
                nome=destino["nome"],
                citados=len(citados),
                status="erro",
                resultado="Grupo de destino não configurado.",
            )
            return {
                "executado": False,
                "status": "erro",
                "motivo": "grupo de destino não configurado",
            }

        texto = servico_mensagens.montar(
            citados, fonte, servico_pessoas.formatar_data(agora.day, agora.month)
        )
        ok, retorno = evolution.enviar_texto(
            settings.evolution_instance, destino["jid"], texto
        )

        _salvar(
            session,
            registro,
            data=data,
            fonte=fonte,
            destino=destino["jid"],
            nome=destino["nome"],
            citados=len(citados),
            status="enviado" if ok else "erro",
            resultado=retorno,
        )

        return {
            "executado": ok,
            "status": "enviado" if ok else "erro",
            "citados": len(citados),
            "destino": destino["nome"],
            "resultado": retorno,
        }


def _salvar(
    session: Session,
    registro: Disparo | None,
    *,
    data: str,
    fonte: str,
    destino: str,
    nome: str,
    citados: int,
    status: str,
    resultado: str,
) -> None:
    item = registro or Disparo(data=data, fonte=fonte)
    item.destino = destino
    item.nome = nome
    item.citados = citados
    item.status = status
    item.resultado = (resultado or "")[:2000]
    item.executado_em = datetime.utcnow()
    session.add(item)
    session.commit()


def _laco() -> None:
    while True:
        try:
            processar()
        except Exception:  # noqa: BLE001 - a thread não pode morrer
            pass
        time.sleep(INTERVALO)


def iniciar() -> None:
    global _iniciado
    with _trava:
        if _iniciado:
            return
        _iniciado = True

    threading.Thread(target=_laco, name="disparo-automatico", daemon=True).start()
