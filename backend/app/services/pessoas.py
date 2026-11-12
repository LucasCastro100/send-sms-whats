"""Pessoas (aniversariantes) e regras de normalização compartilhadas."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from ..config import settings
from ..models import MODELOS_PESSOA, PessoaBase, User

FONTES = ("icm", "zoom")

ARQUIVO_GENEROS = "generos.json"
ARQUIVO_EXCLUSOES = "exclusoes.json"


def fontes_do_usuario(user: User) -> tuple[str, ...]:
    """Fontes que o usuário pode consultar — a lista do Zoom é só do admin."""
    return FONTES if user.admin else ("icm",)

MESES = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]


def normalizar_nome(nome: object) -> str:
    """Maiúsculas e espaços simples — igual ao `generos.json` do Streamlit."""
    return re.sub(r"\s+", " ", str(nome or "")).strip().upper()


def normalizar_telefone(valor: object, ddd_padrao: str = "34") -> str:
    """Só dígitos, com DDD 34 quando faltar e DDI 55 quando faltar.

    O sistema da igreja exporta telefone em formatos diferentes: com DDD,
    sem DDD, com DDI. O padrão do painel é `55` + DDD + número.
    """
    digitos = re.sub(r"\D", "", str(valor or ""))
    if not digitos:
        return ""

    digitos = digitos.lstrip("0")
    if len(digitos) in (8, 9):
        digitos = ddd_padrao + digitos
    if len(digitos) in (10, 11):
        return "55" + digitos
    return digitos


def idade(pessoa: PessoaBase, hoje: Optional[date] = None) -> Optional[int]:
    """Idade em anos, quando o ano de nascimento é conhecido."""
    if not pessoa.ano:
        return None
    referencia = hoje or date.today()
    dia = pessoa.dia or 1
    mes = pessoa.mes or 1
    return referencia.year - pessoa.ano - (
        (referencia.month, referencia.day) < (mes, dia)
    )


def dias_sem_visita(pessoa: PessoaBase, hoje: Optional[date] = None) -> Optional[int]:
    """Dias desde a última visita — a data manda; o número é só histórico."""
    if pessoa.ultima_visita:
        referencia = hoje or date.today()
        return max(0, (referencia - pessoa.ultima_visita).days)
    return pessoa.dias_sem_visita


def formatar_data(dia: Optional[int], mes: Optional[int]) -> str:
    if not dia or not mes:
        return ""
    return f"{int(dia):02d}/{int(mes):02d}"


def nome_mes(mes: Optional[int]) -> str:
    if not mes or not 1 <= int(mes) <= 12:
        return ""
    return MESES[int(mes) - 1]


def modelo(fonte: str) -> type:
    """Classe/tabela da fonte (`icm` ou `zoom`)."""
    try:
        return MODELOS_PESSOA[fonte.lower()]
    except KeyError:
        raise ValueError(f"Fonte inválida: {fonte}")


def _listar_fonte(
    session: Session,
    fonte: str,
    busca: Optional[str],
    incluir_inativos: bool,
    grupos: Optional[set[str]] = None,
    apenas_mulheres: bool = False,
) -> list:
    tabela = modelo(fonte)
    consulta = select(tabela)
    if not incluir_inativos:
        consulta = consulta.where(tabela.ativo == True)  # noqa: E712
    if busca and busca.strip():
        termo = f"%{normalizar_nome(busca)}%"
        consulta = consulta.where(tabela.nome_chave.like(termo))

    # Só o ICM tem grupos de assistência; o Zoom continua global.
    if grupos is not None and fonte == "icm":
        if not grupos:
            return []
        consulta = consulta.where(tabela.grupo.in_(sorted(grupos)))

    if apenas_mulheres:
        consulta = consulta.where(tabela.genero == "F")

    consulta = consulta.order_by(tabela.mes, tabela.dia, tabela.nome_chave)
    return list(session.exec(consulta).all())


def listar(
    session: Session,
    fonte: Optional[str] = None,
    busca: Optional[str] = None,
    incluir_inativos: bool = False,
    grupos: Optional[set[str]] = None,
    apenas_mulheres: bool = False,
) -> list:
    fontes = (fonte.lower(),) if fonte else FONTES
    pessoas: list = []
    for nome in fontes:
        pessoas.extend(
            _listar_fonte(
                session,
                nome,
                busca,
                incluir_inativos,
                grupos=grupos,
                apenas_mulheres=apenas_mulheres,
            )
        )
    return pessoas


def contar_por_fonte(session: Session, fontes: tuple[str, ...] = FONTES) -> dict:
    resultado = {}
    for fonte in fontes:
        pessoas = session.exec(select(modelo(fonte))).all()
        resultado[fonte] = {
            "total": len(pessoas),
            "ativos": sum(1 for pessoa in pessoas if pessoa.ativo),
            "excluidos": sum(1 for pessoa in pessoas if pessoa.excluido),
            "sem_genero": sum(1 for pessoa in pessoas if not pessoa.genero),
        }
    return resultado


def aplicar_mudancas(pessoa: PessoaBase, mudancas: dict) -> None:
    """Aplica só os campos preenchidos (vazio no arquivo não apaga o banco)."""
    for campo, valor in mudancas.items():
        if valor in (None, ""):
            continue
        setattr(pessoa, campo, valor)


# ---------------------------------------------------------------------------
# Espelho em `data/*.json` para o disparo do GitHub Actions
# ---------------------------------------------------------------------------
# O workflow do GitHub não tem acesso ao banco: ele lê `data/generos.json` e
# `data/exclusoes.json` do repositório. Sem este espelho, marcar "Não enviar
# SMS" ou trocar o gênero no painel não mudaria a mensagem enviada pelo Git.
def _ler_json(nome: str, padrao: dict) -> dict:
    caminho = Path(settings.data_dir) / nome
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao
    return dados if isinstance(dados, dict) else padrao


def _gravar_json(nome: str, dados: dict) -> None:
    """Grava o espelho. Se a pasta for somente leitura (VPS), não quebra o painel."""
    caminho = Path(settings.data_dir) / nome
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(
            json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        # No servidor o `data/` pode estar montado como somente leitura; quem
        # envia lá é a própria API (lê o banco), então o espelho é opcional.
        pass


def sincronizar_exclusao(nome_chave: str, fonte: str, excluido: bool) -> None:
    """Mantém `exclusoes.json` igual à marcação do painel."""
    fonte = (fonte or "").lower()
    if fonte not in FONTES:
        return

    dados = _ler_json(ARQUIVO_EXCLUSOES, {"icm": [], "zoom": []})
    nomes = {
        normalizar_nome(nome)
        for nome in dados.get(fonte, [])
        if str(nome).strip()
    }
    chave = normalizar_nome(nome_chave)
    if excluido:
        nomes.add(chave)
    else:
        nomes.discard(chave)

    dados[fonte] = sorted(nomes)
    _gravar_json(ARQUIVO_EXCLUSOES, dados)


def sincronizar_genero(
    nome_chave: str, fonte: str, genero: Optional[str]
) -> None:
    """Mantém `generos.json` igual ao gênero salvo no painel."""
    fonte = (fonte or "").lower()
    if fonte not in FONTES:
        return

    dados = _ler_json(ARQUIVO_GENEROS, {"icm": {}, "zoom": {}})
    mapa = dados.get(fonte)
    if not isinstance(mapa, dict):
        mapa = {}

    chave = normalizar_nome(nome_chave)
    if genero in ("M", "F"):
        mapa[chave] = genero
    else:
        mapa.pop(chave, None)

    dados[fonte] = dict(sorted(mapa.items()))
    _gravar_json(ARQUIVO_GENEROS, dados)
