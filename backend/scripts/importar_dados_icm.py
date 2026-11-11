#!/usr/bin/env python
"""Junta os PDFs do sistema da igreja na tabela `icm`.

Uso (a partir de `backend/`):

    .venv/bin/python scripts/importar_dados_icm.py            # só simula
    .venv/bin/python scripts/importar_dados_icm.py --aplicar  # grava no banco

Os arquivos são lidos de `data/entrada/dados_icm/` por padrão:

- ``listagem-geral.pdf``
- ``listagem-membros_g1_contato.pdf``
- ``listagem-membros_g2_contato.pdf``
- ``listagem-membros_g3_contato.pdf``
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlmodel import Session  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import engine, init_db  # noqa: E402
from app.services import dados_icm  # noqa: E402
from app.services import grupos as servico_grupos  # noqa: E402


def _data(texto: str | None) -> date | None:
    if not texto:
        return None
    dia, mes, ano = (int(parte) for parte in texto.split("/"))
    return date(ano, mes, dia)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pasta",
        default=str(Path(settings.data_dir) / "entrada" / "dados_icm"),
        help="Pasta com os PDFs do sistema da igreja.",
    )
    parser.add_argument(
        "--referencia",
        default=None,
        help="Data de referência do S/ Visitas (dd/mm/aaaa). Padrão: a do PDF.",
    )
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Grava no banco. Sem esta opção, apenas simula e desfaz.",
    )
    args = parser.parse_args()

    pasta = Path(args.pasta)
    if not pasta.is_dir():
        print(f"Pasta não encontrada: {pasta}")
        return 1

    print(f"Lendo {pasta}")
    relatorio = dados_icm.juntar(pasta, referencia=_data(args.referencia))
    print()
    print("— Junção —")
    print(relatorio.resumo())
    print("Por grupo:", dados_icm.contar_por_grupo(relatorio.registros))

    init_db()
    with Session(engine) as session:
        resultado = dados_icm.aplicar(session, relatorio, dry_run=not args.aplicar)
        print()
        print("— Banco —")
        print(resultado.resumo())

        if args.aplicar:
            sincronizados = servico_grupos.sincronizar(session)
            print(f"Grupos de assistência sincronizados: {sincronizados}")
            print("\nGravado no banco.")
        else:
            print("\nSimulação: nada foi gravado. Use --aplicar para salvar.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
