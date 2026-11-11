"""Grupos de assistência do ICM e o escopo de acesso de cada usuário."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from ..models import GrupoAssistencia, PessoaICM, User

FUNCOES = ("admin", "lider", "frente")
FUNCAO_PADRAO = "lider"


def normalizar_funcao(valor: object) -> str:
    funcao = str(valor or "").strip().lower()
    return funcao if funcao in FUNCOES else FUNCAO_PADRAO


def funcao_do_usuario(user: User) -> str:
    """Função efetiva: quem é admin sempre aparece como admin."""
    if user.admin:
        return "admin"
    return normalizar_funcao(getattr(user, "funcao", ""))


def sincronizar(session: Session) -> int:
    """Cria os grupos que ainda não existem a partir da coluna `grupo` do ICM."""
    nomes = {
        (nome or "").strip()
        for nome in session.exec(select(PessoaICM.grupo)).all()
        if (nome or "").strip()
    }
    existentes = {
        grupo.nome: grupo
        for grupo in session.exec(select(GrupoAssistencia)).all()
    }

    criados = 0
    for nome in sorted(nomes):
        if nome not in existentes:
            session.add(GrupoAssistencia(nome=nome))
            criados += 1

    if criados:
        session.commit()
    return criados


def listar(session: Session) -> list[GrupoAssistencia]:
    return list(
        session.exec(
            select(GrupoAssistencia)
            .where(GrupoAssistencia.ativo == True)  # noqa: E712
            .order_by(GrupoAssistencia.nome)
        ).all()
    )


def mapa(session: Session) -> dict[str, GrupoAssistencia]:
    """`{nome: grupo}` para achar o responsável pela coluna `grupo` da vida."""
    return {
        grupo.nome: grupo
        for grupo in session.exec(select(GrupoAssistencia)).all()
    }


def atualizar_responsavel(
    session: Session,
    grupo_id: int,
    nome: str,
    whatsapp: str,
) -> Optional[GrupoAssistencia]:
    grupo = session.get(GrupoAssistencia, grupo_id)
    if not grupo:
        return None
    grupo.responsavel_nome = str(nome or "").strip()[:160]
    grupo.responsavel_whatsapp = str(whatsapp or "").strip()[:20]
    session.add(grupo)
    session.commit()
    session.refresh(grupo)
    return grupo


def buscar(session: Session, grupo_id: Optional[int]) -> Optional[GrupoAssistencia]:
    if not grupo_id:
        return None
    return session.get(GrupoAssistencia, grupo_id)


def nome_do_usuario(session: Session, user: User) -> str:
    grupo = buscar(session, user.grupo_id)
    return grupo.nome if grupo else ""


def escopo(session: Session, user: User) -> dict:
    """O que o usuário pode ver nas telas do ICM.

    - admin: tudo;
    - frente: todas as mulheres (de todos os grupos);
    - lider: só as pessoas do grupo de assistência dele.
    """
    funcao = funcao_do_usuario(user)

    if funcao == "admin":
        return {"grupos": None, "apenas_mulheres": False}
    if funcao == "frente":
        return {"grupos": None, "apenas_mulheres": True}

    grupo = buscar(session, user.grupo_id)
    return {
        "grupos": {grupo.nome} if grupo else set(),
        "apenas_mulheres": False,
    }


def pessoas_do_escopo(session: Session, user: User) -> list[PessoaICM]:
    """Vidas do ICM que o usuário pode consultar."""
    from . import pessoas as servico_pessoas

    escopo_atual = escopo(session, user)
    return servico_pessoas.listar(
        session,
        fonte="icm",
        grupos=escopo_atual["grupos"],
        apenas_mulheres=escopo_atual["apenas_mulheres"],
    )


def chaves_do_escopo(session: Session, user: User) -> set[str]:
    return {pessoa.nome_chave for pessoa in pessoas_do_escopo(session, user)}
