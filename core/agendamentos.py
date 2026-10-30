"""Envios avulsos agendados: mensagem + destinatário + data/hora escolhida.

Os agendamentos ficam salvos em `envios_agendados.json`; ao iniciar o app,
os que ainda estão pendentes são registrados novamente no APScheduler.
"""

from __future__ import annotations

from datetime import datetime
import json
import uuid

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import pytz
import streamlit as st

from core.comum import PASTA_RUNTIME, enviar_via_evolution_api

ARQUIVO_AGENDAMENTOS = PASTA_RUNTIME / "envios_agendados.json"
ARQUIVO_LOG = PASTA_RUNTIME / "envios_agendados.log"
FUSO = "America/Sao_Paulo"


def agora() -> datetime:
    """Data/hora atual no horário de Brasília."""
    return datetime.now(pytz.timezone(FUSO))


def _registrar_log(mensagem: str) -> None:
    linha = f"[{agora().strftime('%Y-%m-%d %H:%M:%S')}] {mensagem}"
    print(linha, flush=True)
    try:
        with open(ARQUIVO_LOG, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except OSError:
        pass


def ler_agendamentos() -> list[dict]:
    """Lê a lista de agendamentos salvos (mais recentes primeiro)."""
    try:
        with open(ARQUIVO_AGENDAMENTOS, encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _gravar_agendamentos(lista: list[dict]) -> None:
    with open(ARQUIVO_AGENDAMENTOS, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)


def _atualizar(agendamento_id: str, **campos) -> None:
    lista = ler_agendamentos()
    for item in lista:
        if item.get("id") == agendamento_id:
            item.update(campos)
            break
    _gravar_agendamentos(lista)


def _executar(agendamento_id: str) -> None:
    """Executado pelo APScheduler no horário escolhido (sem interface)."""
    item = next(
        (a for a in ler_agendamentos() if a.get("id") == agendamento_id), None
    )
    if not item:
        _registrar_log(f"Agendamento {agendamento_id} não encontrado. Ignorado.")
        return

    if item.get("status") != "pendente":
        _registrar_log(
            f"Agendamento {agendamento_id} está com status "
            f"'{item.get('status')}'. Nada a fazer."
        )
        return

    sucesso, retorno = enviar_via_evolution_api(item["texto"], item["jid"])
    _atualizar(
        agendamento_id,
        status="enviado" if sucesso else "erro",
        resultado=retorno,
        executado_em=agora().isoformat(timespec="seconds"),
    )
    _registrar_log(
        f"Envio agendado para {item.get('nome')}: "
        f"{'OK' if sucesso else 'FALHA'} - {retorno}"
    )


def _reagendar_pendentes(scheduler: BackgroundScheduler) -> None:
    """Ao subir o app, recria os jobs dos agendamentos que ainda não venceram."""
    agora_ts = agora()

    for item in ler_agendamentos():
        if item.get("status") != "pendente":
            continue

        try:
            quando = datetime.fromisoformat(item["quando"])
        except (KeyError, ValueError):
            _atualizar(item.get("id", ""), status="erro", resultado="data inválida")
            continue

        if quando.tzinfo is None:
            quando = pytz.timezone(FUSO).localize(quando)

        if quando <= agora_ts:
            _atualizar(
                item["id"],
                status="perdido",
                resultado="horário passou enquanto o app estava parado",
            )
            _registrar_log(
                f"Agendamento {item['id']} perdido (horário {quando:%d/%m %H:%M})."
            )
            continue

        scheduler.add_job(
            _executar,
            trigger=DateTrigger(run_date=quando, timezone=FUSO),
            args=[item["id"]],
            id=f"envio_{item['id']}",
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=3600,
        )


@st.cache_resource
def obter_agendador() -> BackgroundScheduler:
    """Agendador único do app (jobs diários + envios agendados)."""
    scheduler = BackgroundScheduler(timezone=FUSO)
    _reagendar_pendentes(scheduler)
    scheduler.start()
    return scheduler


def agendar_envio(
    texto: str,
    destino_jid: str,
    nome_destino: str,
    quando: datetime,
) -> dict:
    """Cria um envio único para a data/hora informada."""
    if quando.tzinfo is None:
        quando = pytz.timezone(FUSO).localize(quando)

    if quando <= agora():
        raise ValueError("O horário escolhido já passou.")

    item = {
        "id": uuid.uuid4().hex[:8],
        "texto": texto,
        "jid": destino_jid,
        "nome": nome_destino,
        "quando": quando.isoformat(timespec="seconds"),
        "status": "pendente",
        "criado_em": agora().isoformat(timespec="seconds"),
        "resultado": "",
    }

    lista = ler_agendamentos()
    lista.append(item)
    _gravar_agendamentos(lista)

    obter_agendador().add_job(
        _executar,
        trigger=DateTrigger(run_date=quando, timezone=FUSO),
        args=[item["id"]],
        id=f"envio_{item['id']}",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=3600,
    )

    _registrar_log(
        f"Agendado para {quando:%d/%m/%Y %H:%M} -> {nome_destino} ({destino_jid})"
    )
    return item


def cancelar_agendamento(agendamento_id: str) -> None:
    """Remove o job (se existir) e marca o agendamento como cancelado."""
    try:
        obter_agendador().remove_job(f"envio_{agendamento_id}")
    except Exception:
        pass

    _atualizar(agendamento_id, status="cancelado")
    _registrar_log(f"Agendamento {agendamento_id} cancelado.")
