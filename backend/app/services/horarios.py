"""Datas e horários do painel.

O banco guarda tudo em UTC (naive). A tela mostra no horário de Brasília, que
não tem mais horário de verão: é sempre UTC-3.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

DESLOCAMENTO = timedelta(hours=-3)


def agora_brasilia() -> datetime:
    """Agora no horário de Brasília, sem timezone (para comparar com a tela)."""
    return datetime.utcnow() + DESLOCAMENTO


def para_utc(local: datetime) -> datetime:
    """Horário de Brasília -> UTC naive (como fica no banco)."""
    return local - DESLOCAMENTO


def para_brasilia(utc: datetime) -> datetime:
    """UTC naive do banco -> horário de Brasília."""
    return utc + DESLOCAMENTO


def de_iso(valor: str) -> Optional[datetime]:
    """Lê um ISO 8601 (com `Z` ou offset) e devolve UTC naive."""
    texto = (valor or "").strip()
    if not texto:
        return None

    try:
        data = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None

    if data.tzinfo is not None:
        data = data.astimezone(timezone.utc).replace(tzinfo=None)
    return data


def formatar(data: Optional[datetime], com_hora: bool = True) -> str:
    if not data:
        return ""
    local = para_brasilia(data)
    if com_hora:
        return local.strftime("%d/%m/%Y %H:%M")
    return local.strftime("%d/%m/%Y")
