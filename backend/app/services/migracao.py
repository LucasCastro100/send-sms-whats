"""Migração única dos arquivos antigos (`data/`) para as tabelas do banco.

Roda no primeiro start, quando as tabelas `icm` e `zoom` estão vazias. Depois
disso a fonte da verdade é o banco: o painel importa PDF/XLS e grava direto nele.

Também separa a antiga tabela `pessoas` (uma só, com coluna `fonte`) nas tabelas
`icm` e `zoom`, preservando gênero/exclusão que já foram ajustados no painel.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import MetaData, Table, inspect
from sqlmodel import Session, select

from ..config import settings
from . import importacao as servico_importacao
from . import pessoas as servico_pessoas


def _normalizar_generos(dados: dict) -> dict:
    return {
        servico_pessoas.normalizar_nome(nome): str(valor).strip().upper()[:1]
        for nome, valor in dados.items()
        if str(nome).strip() and str(valor).strip()
    }


def _carregar_generos(caminho: Path) -> dict:
    """`{fonte: {NOME: "M"|"F"}}`, aceitando o formato antigo (plano)."""
    vazio = {"icm": {}, "zoom": {}}
    if not caminho.exists():
        return vazio

    try:
        dados = json.loads(caminho.read_text("utf-8"))
    except (OSError, ValueError):
        return vazio

    if not isinstance(dados, dict):
        return vazio

    separado = any(isinstance(valor, dict) for valor in dados.values())
    if not separado:
        return {"icm": _normalizar_generos(dados), "zoom": {}}

    return {
        "icm": _normalizar_generos(dados.get("icm", {})),
        "zoom": _normalizar_generos(dados.get("zoom", {})),
    }


def _carregar_exclusoes(caminho: Path) -> dict:
    vazio = {"icm": set(), "zoom": set()}
    if not caminho.exists():
        return vazio

    try:
        dados = json.loads(caminho.read_text("utf-8"))
    except (OSError, ValueError):
        return vazio

    if not isinstance(dados, dict):
        return vazio

    return {
        fonte: {
            servico_pessoas.normalizar_nome(nome)
            for nome in dados.get(fonte, [])
            if str(nome).strip()
        }
        for fonte in ("icm", "zoom")
    }


def _genero_de(nome_chave: str, generos: dict) -> Optional[str]:
    if nome_chave in generos:
        return generos[nome_chave]

    primeiro = nome_chave.split()[0] if nome_chave else ""
    if primeiro and primeiro in generos:
        return generos[primeiro]
    return None


def _tem_pessoas(session: Session) -> bool:
    return any(
        session.exec(select(servico_pessoas.modelo(fonte))).first()
        for fonte in servico_pessoas.FONTES
    )


def separar_tabelas_antigas(session: Session) -> dict:
    """Move a tabela única `pessoas` para `icm`/`zoom` e apaga a antiga."""
    inspetor = inspect(session.get_bind())
    if "pessoas" not in inspetor.get_table_names():
        return {"separado": False, "motivo": "tabela `pessoas` não existe"}

    antiga = Table("pessoas", MetaData(), autoload_with=session.get_bind())
    linhas = session.execute(select(antiga)).mappings().all()

    copiados = {fonte: 0 for fonte in servico_pessoas.FONTES}
    ignorados = 0

    for linha in linhas:
        fonte = str(linha.get("fonte") or "").lower()
        if fonte not in servico_pessoas.FONTES:
            ignorados += 1
            continue

        tabela = servico_pessoas.modelo(fonte)
        chave = linha.get("nome_chave") or servico_pessoas.normalizar_nome(
            linha.get("nome")
        )
        if not chave:
            ignorados += 1
            continue
        if session.exec(select(tabela).where(tabela.nome_chave == chave)).first():
            ignorados += 1
            continue

        session.add(
            tabela(
                nome=linha.get("nome") or chave,
                nome_chave=chave,
                dia=linha.get("dia"),
                mes=linha.get("mes"),
                grupo=linha.get("grupo") or "",
                telefone=linha.get("telefone") or "",
                foto=linha.get("foto") or "",
                genero=linha.get("genero"),
                excluido=bool(linha.get("excluido")),
                ativo=bool(linha.get("ativo", True)),
                criado_em=linha.get("criado_em") or datetime.utcnow(),
                atualizado_em=linha.get("atualizado_em") or datetime.utcnow(),
                visto_em=linha.get("visto_em"),
            )
        )
        copiados[fonte] += 1

    session.commit()
    antiga.drop(session.get_bind())

    return {"separado": True, "copiados": copiados, "ignorados": ignorados}


def migrar_arquivos(session: Session, forcar: bool = False) -> dict:
    """Importa `data.pdf`, CSV do Zoom, `generos.json` e `exclusoes.json`."""
    if not forcar and _tem_pessoas(session):
        return {"migrado": False, "motivo": "já existem pessoas no banco"}

    pasta = Path(settings.data_dir)
    if not pasta.exists():
        return {"migrado": False, "motivo": f"pasta não encontrada: {pasta}"}

    generos = _carregar_generos(pasta / "generos.json")
    exclusoes = _carregar_exclusoes(pasta / "exclusoes.json")
    agora = datetime.utcnow()
    resultado = {"migrado": True, "fontes": {}}

    arquivos = {
        "icm": pasta / "data.pdf",
        "zoom": pasta / "aniversariantes_zoom.csv",
    }

    for fonte, caminho in arquivos.items():
        if not caminho.exists():
            resultado["fontes"][fonte] = {"erro": "arquivo não encontrado"}
            continue

        try:
            linhas, _, avisos = servico_importacao.ler_arquivo(
                caminho.name, caminho.read_bytes()
            )
        except Exception as e:  # noqa: BLE001 - relatório da migração
            resultado["fontes"][fonte] = {"erro": str(e)}
            continue

        inseridos = 0
        tabela = servico_pessoas.modelo(fonte)
        for linha in linhas:
            chave = servico_pessoas.normalizar_nome(linha.get("nome"))
            if not chave:
                continue
            if session.exec(
                select(tabela).where(tabela.nome_chave == chave)
            ).first():
                continue

            session.add(
                tabela(
                    nome=linha["nome"],
                    nome_chave=chave,
                    dia=linha.get("dia"),
                    mes=linha.get("mes"),
                    grupo=linha.get("grupo", ""),
                    telefone=linha.get("telefone", ""),
                    genero=_genero_de(chave, generos[fonte]),
                    excluido=chave in exclusoes[fonte],
                    ativo=True,
                    criado_em=agora,
                    atualizado_em=agora,
                    visto_em=agora,
                )
            )
            inseridos += 1

        resultado["fontes"][fonte] = {"inseridos": inseridos, "avisos": avisos}

    session.commit()
    resultado["total"] = sum(
        len(session.exec(select(servico_pessoas.modelo(fonte))).all())
        for fonte in servico_pessoas.FONTES
    )
    return resultado
