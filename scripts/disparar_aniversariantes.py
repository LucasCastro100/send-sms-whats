"""Disparo diário dos aniversariantes (ICM e Zoom) fora do Streamlit.

É este script que o GitHub Actions executa às 00:00 de Brasília. Também pode
ser rodado na mão, inclusive em modo de teste (sem enviar nada):

    python -m scripts.disparar_aniversariantes
    python -m scripts.disparar_aniversariantes --fonte icm
    python -m scripts.disparar_aniversariantes --dry-run --data 30/10
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

from core import comum  # noqa: E402


def _modo_teste(texto: str, destinatario_jid: str) -> tuple[bool, str]:
    print(
        "--- DRY-RUN: mensagem NÃO enviada ---\n"
        f"Destino: {destinatario_jid}\n"
        f"{texto}\n"
        "------------------------------------",
        flush=True,
    )
    return True, "dry-run"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dispara os aniversariantes do dia para os grupos do ICM e do Zoom."
    )
    parser.add_argument(
        "--fonte",
        choices=["ambos", "icm", "zoom"],
        default="ambos",
        help="Qual lista disparar (padrão: ambos).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Monta e imprime a mensagem sem enviar para o WhatsApp.",
    )
    parser.add_argument(
        "--data",
        metavar="DD/MM",
        default=None,
        help="Data de referência para o teste (padrão: hoje em Brasília).",
    )
    args = parser.parse_args()

    if args.dry_run:
        comum.enviar_via_evolution_api = _modo_teste

    disparos = []
    if args.fonte in ("ambos", "icm"):
        disparos.append(("ICM", comum.disparar_aniversariantes_icm))
    if args.fonte in ("ambos", "zoom"):
        disparos.append(("Zoom", comum.disparar_aniversariantes_zoom))

    falhas = 0
    for nome, disparar in disparos:
        sucesso, retorno = disparar(data_ref=args.data)
        print(f"[{nome}] {'OK' if sucesso else 'FALHA'} - {retorno}", flush=True)
        if not sucesso:
            falhas += 1

    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
