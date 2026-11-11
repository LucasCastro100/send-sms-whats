"""Importação de PDF/planilha: compara com o banco e aplica só o que mudou.

Regras (acordadas com o Lucas):

- a chave é `(fonte, nome normalizado)`; se o arquivo trouxer telefone, o
  telefone tem prioridade e a pessoa é renomeada em vez de duplicada;
- campo vazio no arquivo nunca apaga o que já está no banco;
- gênero e exclusão são manuais: a importação nunca sobrescreve;
- quem está no banco e não aparece no arquivo continua ativo (fica "ausente");
- nome repetido no mesmo arquivo vira conflito (fica o primeiro).
"""

from __future__ import annotations

import io
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
from sqlmodel import Session, select

from ..models import Importacao, PessoaBase
from . import pessoas as servico_pessoas

EXTENSOES_PLANILHA = {".csv", ".tsv", ".txt", ".xlsx", ".xls", ".ods"}

# "12  04/01  FULANO DE TAL  3 - GRUPO X"
PADRAO_PDF = re.compile(r"^(\d+)\s+(\d{2}/\d{2})\s+(.+?)\s+(\d+\s*-.*)$")
PADRAO_PDF_SIMPLES = re.compile(r"^(\d+)\s+(\d{2}/\d{2})\s+(.+)$")


# ---------------------------------------------------------------------------
# Normalização de colunas e datas
# ---------------------------------------------------------------------------
def _sem_acento(texto: object) -> str:
    return (
        unicodedata.normalize("NFKD", str(texto))
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def _parse_data(valor: object) -> Tuple[Optional[int], Optional[int]]:
    texto = str(valor or "").strip()
    if not texto:
        return None, None

    achado = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$", texto)
    if achado:
        dia, mes = int(achado.group(1)), int(achado.group(2))
        return (dia, mes) if _data_valida(dia, mes) else (None, None)

    achado = re.match(r"^(\d{4})-(\d{2})-(\d{2})", texto)
    if achado:
        dia, mes = int(achado.group(3)), int(achado.group(2))
        return (dia, mes) if _data_valida(dia, mes) else (None, None)

    achado = re.match(r"^(\d{1,2})[-.](\d{1,2})[-.](\d{2,4})$", texto)
    if achado:
        dia, mes = int(achado.group(1)), int(achado.group(2))
        return (dia, mes) if _data_valida(dia, mes) else (None, None)

    return None, None


def _data_valida(dia: int, mes: int) -> bool:
    return 1 <= dia <= 31 and 1 <= mes <= 12


def _detectar_mapeamento(colunas: list) -> dict:
    """Adivinha qual coluna é nome/data/grupo/telefone/foto."""
    mapa: dict = {}

    for coluna in colunas:
        chave = _sem_acento(coluna).lower()
        if "nome" in chave and "nome" not in mapa:
            mapa["nome"] = coluna
        elif ("nasc" in chave or "data" in chave or "anivers" in chave) and "data" not in mapa:
            mapa["data"] = coluna
        elif ("grupo" in chave or "assist" in chave) and "grupo" not in mapa:
            mapa["grupo"] = coluna
        elif (
            "tel" in chave or "fone" in chave or "whats" in chave or "celular" in chave
        ) and "telefone" not in mapa:
            mapa["telefone"] = coluna
        elif ("foto" in chave or "imagem" in chave) and "foto" not in mapa:
            mapa["foto"] = coluna

    return mapa


def _mapear_por_conteudo(tabela: pd.DataFrame) -> dict:
    """Sem cabeçalho: acha a coluna de data (dd/mm) e a de nomes."""
    mapa: dict = {}

    for coluna in tabela.columns:
        valores = [str(valor) for valor in tabela[coluna].tolist() if str(valor).strip()]
        if not valores:
            continue

        datas = sum(1 for valor in valores if _parse_data(valor)[1] is not None)
        if datas >= max(1, len(valores) // 2) and "data" not in mapa:
            mapa["data"] = coluna

    if "data" not in mapa:
        return {}

    for coluna in tabela.columns:
        if coluna == mapa["data"]:
            continue
        valores = [str(valor) for valor in tabela[coluna].tolist() if str(valor).strip()]
        if not valores:
            continue
        letras = sum(1 for valor in valores if re.search(r"[A-Za-zÀ-ÿ]", valor))
        if letras >= max(1, len(valores) // 2):
            mapa["nome"] = coluna
            break

    return mapa


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------
def _ler_pdf(conteudo: bytes) -> Tuple[list, list]:
    from pypdf import PdfReader

    linhas: list = []
    avisos: list = []

    leitor = PdfReader(io.BytesIO(conteudo))
    for pagina in leitor.pages:
        texto = pagina.extract_text() or ""
        for bruta in texto.splitlines():
            bruta = bruta.strip()
            if not bruta:
                continue

            achado = PADRAO_PDF.match(bruta)
            if achado:
                dia, mes = _parse_data(achado.group(2))
                linhas.append(
                    {
                        "nome": achado.group(3),
                        "dia": dia,
                        "mes": mes,
                        "grupo": achado.group(4).strip(),
                        "telefone": "",
                        "foto": "",
                    }
                )
                continue

            achado = PADRAO_PDF_SIMPLES.match(bruta)
            if achado:
                dia, mes = _parse_data(achado.group(2))
                linhas.append(
                    {
                        "nome": achado.group(3),
                        "dia": dia,
                        "mes": mes,
                        "grupo": "",
                        "telefone": "",
                        "foto": "",
                    }
                )

    if not linhas:
        avisos.append(
            "Nenhuma linha no formato do PDF do ICM (número, data e nome) foi "
            "encontrada. Se o PDF for uma tabela, envie a planilha (XLS/CSV)."
        )

    return linhas, avisos


def _ler_planilha(
    nome: str,
    conteudo: bytes,
    mapeamento: Optional[dict] = None,
) -> Tuple[list, dict, list]:
    extensao = Path(nome).suffix.lower()
    buffer = io.BytesIO(conteudo)
    avisos: list = []

    if extensao in {".csv", ".tsv", ".txt"}:
        bruto = pd.DataFrame()
        for separador in [",", ";", "\t"]:
            try:
                buffer.seek(0)
                tentativa = pd.read_csv(
                    buffer,
                    sep=separador,
                    engine="python",
                    dtype=str,
                    keep_default_na=False,
                    skip_blank_lines=True,
                )
                if tentativa.shape[1] > 1:
                    bruto = tentativa
                    break
                if bruto.empty:
                    bruto = tentativa
            except Exception:
                continue
    else:
        abas = pd.read_excel(buffer, sheet_name=None, dtype=str)
        abas = {aba: tabela for aba, tabela in abas.items() if not tabela.empty}
        if not abas:
            return [], {}, ["A planilha está vazia."]
        if len(abas) > 1:
            avisos.append(
                f"A planilha tem {len(abas)} abas; usando a primeira "
                f"({list(abas)[0]})."
            )
        bruto = next(iter(abas.values()))

    if bruto.empty:
        return [], {}, ["Não consegui ler nenhuma linha do arquivo."]

    bruto.columns = [str(coluna).strip() for coluna in bruto.columns]

    mapa = dict(mapeamento or {})
    if not mapa:
        mapa = _detectar_mapeamento(list(bruto.columns))
        if not ("nome" in mapa and "data" in mapa):
            alternativo = _mapear_por_conteudo(bruto)
            if alternativo:
                mapa = {**alternativo, **mapa}

    if "nome" not in mapa or "data" not in mapa:
        raise ValueError(
            "Não identifiquei as colunas de nome e data. Cabeçalhos "
            f"encontrados: {', '.join(map(str, bruto.columns))}. "
            "Renomeie para 'Nome' e 'Data Nasc.' ou envie o mapeamento."
        )

    linhas: list = []
    for _, linha in bruto.iterrows():
        nome_valor = str(linha.get(mapa["nome"], "")).strip()
        if not nome_valor:
            continue

        dia, mes = _parse_data(linha.get(mapa["data"], ""))
        if mes is None:
            avisos.append(f"Data inválida para {nome_valor}: ignorado.")
            continue

        def valor(campo: str) -> str:
            coluna = mapa.get(campo)
            if coluna is None:
                return ""
            return str(linha.get(coluna, "")).strip()

        linhas.append(
            {
                "nome": nome_valor,
                "dia": dia,
                "mes": mes,
                "grupo": valor("grupo"),
                "telefone": servico_pessoas.normalizar_telefone(valor("telefone")),
                "foto": valor("foto"),
            }
        )

    return linhas, mapa, avisos


def ler_arquivo(
    nome: str,
    conteudo: bytes,
    mapeamento: Optional[dict] = None,
) -> Tuple[list, dict, list]:
    """Devolve `(linhas, mapeamento, avisos)`."""
    extensao = Path(nome).suffix.lower()

    if extensao == ".pdf":
        linhas, avisos = _ler_pdf(conteudo)
        return linhas, {}, avisos

    if extensao in EXTENSOES_PLANILHA:
        return _ler_planilha(nome, conteudo, mapeamento)

    raise ValueError(f"Formato não suportado: {extensao or 'sem extensão'}")


# ---------------------------------------------------------------------------
# Diff (sem gravar nada)
# ---------------------------------------------------------------------------
def analisar(session: Session, fonte: str, linhas: list) -> dict:
    fonte = fonte.lower()
    tabela = servico_pessoas.modelo(fonte)
    existentes = list(session.exec(select(tabela)).all())
    por_chave = {pessoa.nome_chave: pessoa for pessoa in existentes}
    por_telefone = {
        pessoa.telefone: pessoa for pessoa in existentes if pessoa.telefone
    }

    novos: list = []
    alterados: list = []
    iguais: list = []
    conflitos: list = []
    vistos: set = set()

    for linha in linhas:
        chave = servico_pessoas.normalizar_nome(linha.get("nome"))
        if not chave:
            conflitos.append({"nome": str(linha.get("nome") or ""), "motivo": "sem nome"})
            continue

        if chave in vistos:
            conflitos.append({"nome": linha["nome"], "motivo": "nome repetido no arquivo"})
            continue
        vistos.add(chave)

        atual = por_chave.get(chave)
        renomeado_de = None

        if atual is None and linha.get("telefone"):
            atual = por_telefone.get(linha["telefone"])
            if atual is not None and atual.nome_chave in vistos:
                atual = None
            elif atual is not None:
                renomeado_de = atual.nome
                vistos.add(atual.nome_chave)

        if atual is None:
            novos.append(
                {
                    "nome": linha["nome"],
                    "dia": linha.get("dia"),
                    "mes": linha.get("mes"),
                    "data": servico_pessoas.formatar_data(linha.get("dia"), linha.get("mes")),
                    "grupo": linha.get("grupo", ""),
                    "telefone": linha.get("telefone", ""),
                }
            )
            continue

        mudancas = _comparar(atual, linha)
        if renomeado_de:
            mudancas.insert(0, {"campo": "nome", "de": renomeado_de, "para": linha["nome"]})

        if mudancas:
            alterados.append(
                {
                    "id": int(atual.id or 0),
                    "nome": linha["nome"],
                    "mudancas": mudancas,
                }
            )
        else:
            iguais.append({"id": int(atual.id or 0), "nome": atual.nome})

    ausentes = [
        {
            "id": int(pessoa.id or 0),
            "nome": pessoa.nome,
            "data": servico_pessoas.formatar_data(pessoa.dia, pessoa.mes),
            "visto_em": pessoa.visto_em.strftime("%d/%m/%Y") if pessoa.visto_em else "",
        }
        for pessoa in existentes
        if pessoa.ativo and pessoa.nome_chave not in vistos
    ]

    ausentes.sort(key=lambda item: item["nome"])

    return {
        "fonte": fonte,
        "total_linhas": len(linhas),
        "novos": novos,
        "alterados": alterados,
        "iguais": iguais,
        "ausentes": ausentes,
        "conflitos": conflitos,
        "resumo": {
            "novos": len(novos),
            "alterados": len(alterados),
            "iguais": len(iguais),
            "ausentes": len(ausentes),
            "conflitos": len(conflitos),
        },
    }


def _comparar(pessoa: PessoaBase, linha: dict) -> list:
    mudancas: list = []

    def comparar(campo: str, atual, novo, rotulo: str) -> None:
        if novo in (None, ""):
            return
        if str(atual or "") != str(novo):
            mudancas.append({"campo": rotulo, "de": atual or "", "para": novo})

    comparar("dia", pessoa.dia, linha.get("dia"), "dia")
    comparar("mes", pessoa.mes, linha.get("mes"), "mês")
    comparar("grupo", pessoa.grupo, linha.get("grupo"), "grupo")
    comparar("telefone", pessoa.telefone, linha.get("telefone"), "telefone")
    comparar("foto", pessoa.foto, linha.get("foto"), "foto")

    return mudancas


# ---------------------------------------------------------------------------
# Aplicação
# ---------------------------------------------------------------------------
def aplicar(
    session: Session,
    fonte: str,
    linhas: list,
    arquivo: str,
    formato: str,
    usuario_id: Optional[int] = None,
    usuario: str = "",
    modo: str = "mesclar",
    igreja_id: Optional[int] = None,
) -> dict:
    diff = analisar(session, fonte, linhas)
    tabela = servico_pessoas.modelo(fonte)
    agora = datetime.utcnow()
    # Igreja das vidas importadas: só o ICM tem o vínculo.
    vinculo = igreja_id if fonte == "icm" else None

    for novo in diff["novos"]:
        chave = servico_pessoas.normalizar_nome(novo["nome"])
        session.add(
            tabela(
                nome=novo["nome"],
                nome_chave=chave,
                dia=_dia(novo.get("dia")),
                mes=_mes(novo.get("mes")),
                grupo=novo["grupo"],
                telefone=novo["telefone"],
                igreja_id=vinculo,
                ativo=True,
                excluido=False,
                criado_em=agora,
                atualizado_em=agora,
                visto_em=agora,
            )
        )

    for alterado in diff["alterados"]:
        pessoa = session.get(tabela, alterado["id"])
        if not pessoa:
            continue

        # Vida já cadastrada e sem igreja? A importação preenche o vínculo.
        if vinculo is not None and getattr(pessoa, "igreja_id", None) is None:
            pessoa.igreja_id = vinculo

        for mudanca in alterado["mudancas"]:
            campo = mudanca["campo"]
            valor = mudanca["para"]

            if campo == "nome":
                pessoa.nome = str(valor)
                pessoa.nome_chave = servico_pessoas.normalizar_nome(valor)
            elif campo == "dia":
                pessoa.dia = int(valor)
            elif campo == "mês":
                pessoa.mes = int(valor)
            elif campo == "grupo":
                pessoa.grupo = str(valor)
            elif campo == "telefone":
                pessoa.telefone = str(valor)
            elif campo == "foto":
                pessoa.foto = str(valor)

        pessoa.atualizado_em = agora
        pessoa.visto_em = agora
        session.add(pessoa)

    for igual in diff["iguais"]:
        pessoa = session.get(tabela, igual["id"])
        if pessoa:
            if vinculo is not None and getattr(pessoa, "igreja_id", None) is None:
                pessoa.igreja_id = vinculo
            pessoa.visto_em = agora
            session.add(pessoa)

    registro = Importacao(
        arquivo=arquivo[:200],
        formato=formato[:10],
        fonte=fonte.lower(),
        modo=modo,
        usuario_id=usuario_id,
        usuario=usuario[:40],
        inseridos=diff["resumo"]["novos"],
        atualizados=diff["resumo"]["alterados"],
        iguais=diff["resumo"]["iguais"],
        ausentes=diff["resumo"]["ausentes"],
        conflitos=diff["resumo"]["conflitos"],
        detalhes=json.dumps(
            {
                "novos": diff["novos"][:50],
                "alterados": diff["alterados"][:50],
                "conflitos": diff["conflitos"][:50],
            },
            ensure_ascii=False,
        )[:20000],
        criado_em=agora,
    )

    session.add(registro)
    session.commit()

    return {
        "importacao_id": int(registro.id or 0),
        **diff["resumo"],
        "ausentes_lista": diff["ausentes"],
    }


def _dia(valor) -> Optional[int]:
    try:
        return int(valor) if valor not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _mes(valor) -> Optional[int]:
    return _dia(valor)
