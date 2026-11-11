"""Cache em disco para chamadas lentas da Evolution (grupos e contatos).

A listagem de grupos pode levar minutos (ou travar) no servidor da Evolution.
Por isso a busca roda em segundo plano e o resultado fica salvo em
`backend/data/cache/`, para a tela responder na hora.
"""

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
from pathlib import Path
from typing import Callable, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = BACKEND_DIR / "data" / "cache"

# Intervalo mínimo entre tentativas automáticas (evita martelar a Evolution).
COOLDOWN = 20

_lock = threading.Lock()
_em_andamento = set()
_erros = {}
_ultima_tentativa = {}
_memoria = {}


def _slug(texto: str) -> str:
    sem_acento = (
        unicodedata.normalize("NFKD", str(texto))
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento).strip("-").lower() or "item"


def chave(tipo: str, instancia: str) -> str:
    return f"{tipo}-{_slug(instancia)}"


def _arquivo(chave_: str) -> Path:
    return CACHE_DIR / f"{chave_}.json"


def ler(chave_: str) -> Tuple[Optional[dict], Optional[float]]:
    """`(dados, salvo_em)` do cache (memória ou disco)."""
    with _lock:
        em_memoria = _memoria.get(chave_)
    if em_memoria:
        return em_memoria[1], em_memoria[0]

    caminho = _arquivo(chave_)
    if not caminho.exists():
        return None, None

    try:
        payload = json.loads(caminho.read_text("utf-8"))
    except (ValueError, OSError):
        return None, None

    dados = payload.get("dados")
    if not isinstance(dados, dict):
        return None, None

    salvo_em = float(payload.get("salvo_em") or 0)
    with _lock:
        _memoria[chave_] = (salvo_em, dados)
    return dados, salvo_em


def sincronizando(chave_: str) -> bool:
    with _lock:
        return chave_ in _em_andamento


def erro(chave_: str) -> Optional[str]:
    with _lock:
        return _erros.get(chave_)


def sincronizar(
    chave_: str,
    buscar: Callable[[], Tuple[dict, Optional[str]]],
    forcar: bool = False,
) -> bool:
    """Busca em segundo plano. `False` quando já existe uma em andamento."""
    with _lock:
        if chave_ in _em_andamento:
            return False

        agora = time.time()
        if not forcar and agora - _ultima_tentativa.get(chave_, 0) < COOLDOWN:
            return False

        _em_andamento.add(chave_)
        _ultima_tentativa[chave_] = agora
        _erros.pop(chave_, None)

    def trabalhar() -> None:
        try:
            dados, falha = buscar()
        except Exception as e:  # noqa: BLE001 - erro vai para a tela
            dados, falha = {}, f"Falha inesperada: {e}"

        with _lock:
            if falha:
                _erros[chave_] = str(falha)
            elif dados:
                salvo_em = time.time()
                _memoria[chave_] = (salvo_em, dados)
                try:
                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    _arquivo(chave_).write_text(
                        json.dumps(
                            {"salvo_em": salvo_em, "dados": dados},
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                except OSError:
                    pass
            _em_andamento.discard(chave_)

    threading.Thread(target=trabalhar, daemon=True).start()
    return True
