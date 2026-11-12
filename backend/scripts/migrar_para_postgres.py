#!/usr/bin/env python
"""Copia o banco local (SQLite) para o Postgres da VPS.

Uso (a partir de `backend/`):

    # confira o que seria copiado (não grava nada)
    .venv/bin/python scripts/migrar_para_postgres.py --destino "$DATABASE_URL"

    # copia de verdade (esvazia as tabelas do destino antes)
    .venv/bin/python scripts/migrar_para_postgres.py --destino "$DATABASE_URL" --aplicar

A origem padrão é `backend/data/app.db`. O destino é uma URL do SQLAlchemy,
por exemplo:

    postgresql+psycopg://checkbirthday:senha@127.0.0.1:5432/checkbirthday

Se a VPS estiver com o Postgres publicado só no host (sem expor a porta), rode
o script de dentro dela (ou faça um túnel SSH):

    ssh -L 5432:127.0.0.1:5432 usuario@vps
    .venv/bin/python scripts/migrar_para_postgres.py --destino ... --aplicar

As tabelas são criadas com o mesmo esquema do app. Os ids são preservados e as
sequências do Postgres são ajustadas para o próximo registro não colidir.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine, func, inspect, select, text  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from app import models  # noqa: E402,F401  (registra as tabelas)
from app.config import settings  # noqa: E402


def _url_sqlite(padrao: str) -> str:
    if padrao.startswith("sqlite:///"):
        return padrao
    return f"sqlite:///{BACKEND_DIR / 'data' / 'app.db'}"


def _contar(engine, tabela: str) -> int:
    with engine.connect() as conexao:
        return int(conexao.execute(text(f'SELECT COUNT(*) FROM "{tabela}"')).scalar() or 0)


def _ajustar_sequencias(conexao) -> None:
    """Depois de copiar ids na mão, o próximo INSERT precisa continuar deles."""
    for tabela in SQLModel.metadata.sorted_tables:
        colunas = {coluna.name for coluna in tabela.columns}
        if "id" not in colunas:
            continue
        conexao.execute(
            text(
                "SELECT setval("
                "pg_get_serial_sequence(:tabela, 'id'), "
                f'COALESCE((SELECT MAX(id) FROM "{tabela.name}"), 0) + 1, '
                "false)"
            ),
            {"tabela": tabela.name},
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copia o SQLite local para o Postgres da VPS."
    )
    parser.add_argument(
        "--origem",
        default=settings.database_url,
        help="URL do banco de origem (padrão: o DATABASE_URL atual, SQLite).",
    )
    parser.add_argument(
        "--destino",
        required=True,
        help="URL do Postgres de destino (postgresql+psycopg://...).",
    )
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Grava de verdade. Sem esta opção só mostra o resumo.",
    )
    args = parser.parse_args()

    origem_url = _url_sqlite(args.origem)
    if args.destino.startswith("sqlite"):
        print("O destino precisa ser Postgres (postgresql+psycopg://...).")
        return 1
    if origem_url == args.destino:
        print("Origem e destino são o mesmo banco.")
        return 1

    origem = create_engine(origem_url)
    destino = create_engine(args.destino, pool_pre_ping=True)

    tabelas_origem = set(inspect(origem).get_table_names())
    tabelas = [
        tabela
        for tabela in SQLModel.metadata.sorted_tables
        if tabela.name in tabelas_origem
    ]
    if not tabelas:
        print("Nenhuma tabela encontrada na origem. O caminho está certo?")
        return 1

    print(f"origem : {origem_url}")
    print(f"destino: {args.destino}")
    print()

    with destino.connect() as conexao_destino:
        existentes = set(inspect(destino).get_table_names())
        ja_tem_dados = any(
            _contar(destino, tabela.name) for tabela in tabelas if tabela.name in existentes
        )

    SQLModel.metadata.create_all(destino)

    with origem.connect() as conexao_origem:
        resumo = []
        for tabela in tabelas:
            total = conexao_origem.execute(
                select(func.count()).select_from(tabela)
            ).scalar()
            resumo.append((tabela.name, int(total or 0)))

    for nome, total in resumo:
        print(f"  {nome:<24} {total:>5} registro(s)")

    if not args.aplicar:
        print("\nSimulação: nada foi gravado. Rode de novo com --aplicar.")
        return 0

    if ja_tem_dados:
        print("\nO destino já tem dados. Esvaziando as tabelas antes de copiar...")

    with destino.begin() as conexao_destino:
        nomes = ", ".join(f'"{tabela.name}"' for tabela in tabelas)
        conexao_destino.execute(text(f"TRUNCATE {nomes} RESTART IDENTITY CASCADE"))

        with origem.connect() as conexao_origem:
            for tabela in tabelas:
                linhas = (
                    conexao_origem.execute(select(tabela)).mappings().all()
                )
                if not linhas:
                    continue
                conexao_destino.execute(tabela.insert(), [dict(linha) for linha in linhas])

        _ajustar_sequencias(conexao_destino)

    print("\nConferindo o destino...")
    with destino.connect() as conexao_destino:
        for tabela in tabelas:
            total = conexao_destino.execute(
                select(func.count()).select_from(tabela)
            ).scalar()
            print(f"  {tabela.name:<24} {int(total or 0):>5} registro(s)")

    print("\nPronto. Ajuste o DATABASE_URL da API para o Postgres e reinicie.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
