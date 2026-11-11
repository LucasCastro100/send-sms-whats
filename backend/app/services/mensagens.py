"""Montagem das mensagens de aniversário (mesmo texto do Streamlit)."""

from __future__ import annotations

from typing import Optional

from ..config import settings

ICONE_ANIVERSARIANTE = "🥳"
ICONE_IRMA = "👧🎉"
ICONE_IRMAO = "👦🎉"


def destino(fonte: str) -> dict:
    """Grupo de destino configurado para a fonte."""
    if fonte == "zoom":
        return {"jid": settings.jid_grupo_zoom, "nome": settings.nome_grupo_zoom}
    return {"jid": settings.jid_grupo_icm, "nome": settings.nome_grupo_icm}


def _icone(pessoa) -> str:
    return ICONE_IRMA if (pessoa.genero or "").upper() == "F" else ICONE_IRMAO


def montar(pessoas: list, fonte: str, data_str: str) -> str:
    """Texto enviado ao grupo. Vazio quando não há ninguém."""
    if not pessoas:
        return ""

    if fonte == "zoom":
        linhas = [
            f"{_icone(pessoa)} Parabéns, *{pessoa.nome}*! "
            "Que o Senhor abençoe grandemente a sua vida! 🎂🎈"
            for pessoa in pessoas
        ]
        return f"🎉 *ANIVERSARIANTES DO DIA ({data_str})* 🎉\n\n" + "\n".join(linhas)

    linhas = [f"• {_icone(pessoa)} *{pessoa.nome}*" for pessoa in pessoas]
    generos = [(pessoa.genero or "").upper() for pessoa in pessoas]

    if len(pessoas) == 1:
        abertura = (
            "Hoje é dia de comemorar a vida da nossa irmã"
            if generos[0] == "F"
            else "Hoje é dia de comemorar a vida do nosso irmão"
        )
        fechamento = (
            "Desejamos que o Senhor abençoe grandemente a sua vida! Parabéns! 🎂🎈"
        )
    elif all(genero == "F" for genero in generos):
        abertura = "Hoje é dia de comemorar a vida das nossas irmãs"
        fechamento = (
            "Desejamos que o Senhor abençoe grandemente a vida de cada uma! "
            "Parabéns! 🎂🎈"
        )
    else:
        abertura = "Hoje é dia de comemorar a vida dos nossos irmãos"
        fechamento = (
            "Desejamos que o Senhor abençoe grandemente a vida de cada um! "
            "Parabéns! 🎂🎈"
        )

    return (
        f"🎉 *ANIVERSARIANTES DO DIA ({data_str})* 🎉\n\n"
        f"{abertura}: {ICONE_ANIVERSARIANTE}\n\n"
        + "\n".join(linhas)
        + "\n\n"
        + fechamento
    )


def do_dia(pessoas: list, dia: Optional[int], mes: Optional[int]) -> list:
    """Aniversariantes ativos da data, sem quem está marcado para não citar."""
    return [
        pessoa
        for pessoa in pessoas
        if pessoa.ativo
        and not pessoa.excluido
        and pessoa.dia == dia
        and pessoa.mes == mes
    ]


def da_data(pessoas: list, dia: Optional[int], mes: Optional[int]) -> list:
    """Todos os aniversariantes ativos da data, inclusive os não citados."""
    return [
        pessoa
        for pessoa in pessoas
        if pessoa.ativo and pessoa.dia == dia and pessoa.mes == mes
    ]
