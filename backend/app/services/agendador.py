"""Envio dos agendamentos pendentes, em segundo plano.

O Streamlit fazia isso num laço dentro do processo. Aqui é uma thread daemon
iniciada no `lifespan` do FastAPI: a cada 30 s ela procura o que já venceu e
dispara pela instância que agendou.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime

from sqlmodel import Session, select

from ..db import engine
from ..models import Agendamento
from . import evolution

INTERVALO = 30  # segundos
_iniciado = False
_trava = threading.Lock()


def agora_utc() -> datetime:
    return datetime.utcnow()


def processar() -> int:
    """Envia o que já venceu. Devolve quantos foram processados."""
    processados = 0

    with Session(engine) as session:
        vencidos = session.exec(
            select(Agendamento).where(
                Agendamento.status == "pendente",
                Agendamento.quando <= agora_utc(),
            )
        ).all()

        for item in vencidos:
            ok, retorno = evolution.enviar_texto(
                item.instancia, item.destino, item.texto
            )
            item.status = "enviado" if ok else "erro"
            item.resultado = retorno[:2000]
            item.executado_em = agora_utc()
            session.add(item)
            processados += 1

        if processados:
            session.commit()

    return processados


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

    threading.Thread(target=_laco, name="agendador", daemon=True).start()
