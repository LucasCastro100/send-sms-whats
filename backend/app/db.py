"""Banco de dados (SQLite por padrão) e sessão por requisição."""

from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from .config import settings

if settings.database_url.startswith("sqlite:///"):
    caminho = Path(settings.database_url.replace("sqlite:///", "", 1))
    caminho.parent.mkdir(parents=True, exist_ok=True)

connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args, echo=False)

if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _garantir_colunas_novas() -> None:
    """Bancos antigos não têm `users.grupo_id` nem `users.funcao`.

    As tabelas de pessoas ganharam os campos do sistema da igreja
    (situação, categoria, telefones, última visita), então bancos criados
    antes disso recebem as colunas aqui.
    """
    if not settings.database_url.startswith("sqlite"):
        return

    with engine.connect() as conexao:
        colunas = {
            linha[1]
            for linha in conexao.exec_driver_sql("PRAGMA table_info(users)").fetchall()
        }
        if "grupo_id" not in colunas:
            conexao.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN grupo_id INTEGER "
                "REFERENCES grupos_assistencia(id)"
            )
        if "funcao" not in colunas:
            conexao.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN funcao VARCHAR(20) NOT NULL DEFAULT 'lider'"
            )

        # Contatos de quem recebe os avisos de presença.
        colunas_grupos = {
            linha[1]
            for linha in conexao.exec_driver_sql(
                "PRAGMA table_info(grupos_assistencia)"
            ).fetchall()
        }
        if colunas_grupos and "responsavel_nome" not in colunas_grupos:
            conexao.exec_driver_sql(
                "ALTER TABLE grupos_assistencia ADD COLUMN "
                "responsavel_nome VARCHAR(160) NOT NULL DEFAULT ''"
            )
        if colunas_grupos and "responsavel_whatsapp" not in colunas_grupos:
            conexao.exec_driver_sql(
                "ALTER TABLE grupos_assistencia ADD COLUMN "
                "responsavel_whatsapp VARCHAR(20) NOT NULL DEFAULT ''"
            )

        colunas_igrejas = {
            linha[1]
            for linha in conexao.exec_driver_sql(
                "PRAGMA table_info(igrejas)"
            ).fetchall()
        }
        if colunas_igrejas and "pastor_nome" not in colunas_igrejas:
            conexao.exec_driver_sql(
                "ALTER TABLE igrejas ADD COLUMN "
                "pastor_nome VARCHAR(160) NOT NULL DEFAULT ''"
            )
        if colunas_igrejas and "pastor_whatsapp" not in colunas_igrejas:
            conexao.exec_driver_sql(
                "ALTER TABLE igrejas ADD COLUMN "
                "pastor_whatsapp VARCHAR(20) NOT NULL DEFAULT ''"
            )

        novas_pessoas = {
            "ano": "INTEGER",
            "situacao": "VARCHAR(40) NOT NULL DEFAULT ''",
            "categoria": "VARCHAR(40) NOT NULL DEFAULT ''",
            "tel_residencial": "VARCHAR(20) NOT NULL DEFAULT ''",
            "tel_comercial": "VARCHAR(20) NOT NULL DEFAULT ''",
            "celular": "VARCHAR(20) NOT NULL DEFAULT ''",
            "ultima_visita": "DATE",
            "dias_sem_visita": "INTEGER",
            "visitas_referencia": "DATE",
        }
        for tabela in ("icm", "zoom"):
            existentes = {
                linha[1]
                for linha in conexao.exec_driver_sql(
                    f"PRAGMA table_info({tabela})"
                ).fetchall()
            }
            if not existentes:
                continue
            for nome, tipo in novas_pessoas.items():
                if nome not in existentes:
                    conexao.exec_driver_sql(
                        f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}"
                    )

        # Vínculo com a igreja: só a lista ICM tem (o Zoom não passa de igreja).
        existentes_icm = {
            linha[1]
            for linha in conexao.exec_driver_sql("PRAGMA table_info(icm)").fetchall()
        }
        if existentes_icm and "igreja_id" not in existentes_icm:
            conexao.exec_driver_sql(
                "ALTER TABLE icm ADD COLUMN igreja_id INTEGER REFERENCES igrejas(id)"
            )

        _migrar_presenca_por_tipo(conexao)
        conexao.commit()


def _migrar_presenca_por_tipo(conexao) -> None:  # noqa: ANN001
    """Adiciona `tipo` em `presencas` e `faltas` (culto x Escola Bíblica).

    O SQLite não remove a constraint antiga (`dia` único / `dia+nome` único),
    então as duas tabelas são recriadas com a chave nova. Os registros que já
    existiam viram `tipo='culto'`.
    """
    colunas_presencas = {
        linha[1]
        for linha in conexao.exec_driver_sql(
            "PRAGMA table_info(presencas)"
        ).fetchall()
    }
    if colunas_presencas and "tipo" not in colunas_presencas:
        conexao.exec_driver_sql(
            """
            CREATE TABLE presencas_nova (
                id INTEGER PRIMARY KEY,
                dia VARCHAR(10) NOT NULL,
                tipo VARCHAR(20) NOT NULL DEFAULT 'culto',
                criado_em DATETIME,
                atualizado_em DATETIME,
                CONSTRAINT uq_presencas_dia_tipo UNIQUE (dia, tipo)
            )
            """
        )
        conexao.exec_driver_sql(
            """
            INSERT INTO presencas_nova (id, dia, tipo, criado_em, atualizado_em)
            SELECT id, dia, 'culto', criado_em, atualizado_em FROM presencas
            """
        )
        conexao.exec_driver_sql("DROP TABLE presencas")
        conexao.exec_driver_sql(
            "ALTER TABLE presencas_nova RENAME TO presencas"
        )
        conexao.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_presencas_dia ON presencas (dia)"
        )
        conexao.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_presencas_tipo ON presencas (tipo)"
        )

    colunas_faltas = {
        linha[1]
        for linha in conexao.exec_driver_sql("PRAGMA table_info(faltas)").fetchall()
    }
    if colunas_faltas and "tipo" not in colunas_faltas:
        conexao.exec_driver_sql(
            """
            CREATE TABLE faltas_nova (
                id INTEGER PRIMARY KEY,
                dia VARCHAR(10) NOT NULL,
                tipo VARCHAR(20) NOT NULL DEFAULT 'culto',
                nome VARCHAR(160) NOT NULL DEFAULT '',
                nome_chave VARCHAR(160) NOT NULL,
                CONSTRAINT uq_faltas_dia_tipo_nome
                    UNIQUE (dia, tipo, nome_chave)
            )
            """
        )
        conexao.exec_driver_sql(
            """
            INSERT INTO faltas_nova (id, dia, tipo, nome, nome_chave)
            SELECT id, dia, 'culto', nome, nome_chave FROM faltas
            """
        )
        conexao.exec_driver_sql("DROP TABLE faltas")
        conexao.exec_driver_sql("ALTER TABLE faltas_nova RENAME TO faltas")
        conexao.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_faltas_dia ON faltas (dia)"
        )
        conexao.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_faltas_tipo ON faltas (tipo)"
        )
        conexao.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_faltas_nome_chave ON faltas (nome_chave)"
        )


def init_db() -> None:
    from . import models  # noqa: F401  (registra as tabelas)

    SQLModel.metadata.create_all(engine)
    _garantir_colunas_novas()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
