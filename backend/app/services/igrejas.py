"""Igrejas de origem das vidas da lista ICM."""

from __future__ import annotations

from sqlmodel import Session, select

from ..models import Igreja, PessoaICM

# Criada no primeiro start para receber as vidas que já estavam no banco
# (todas do ICM vieram dela). Migrações futuras de outras igrejas são
# cadastradas pelo admin na tela Igrejas ou pela importação.
PADRAO = "IGREJA BOA VISTA"


def listar(session: Session) -> list[Igreja]:
    return list(
        session.exec(
            select(Igreja).where(Igreja.ativo == True)  # noqa: E712
            .order_by(Igreja.nome)
        ).all()
    )


def mapa(session: Session) -> dict[int, str]:
    """`{id: nome}` para preencher o nome da igreja nas pessoas."""
    return {
        int(igreja.id or 0): igreja.nome
        for igreja in session.exec(select(Igreja)).all()
    }


def garantir_padrao(session: Session) -> dict:
    """Cria a igreja padrão e vincula as vidas do ICM que não têm igreja.

    Roda uma vez: depois que a primeira igreja existe, o painel manda no
    cadastro e nada é alterado automaticamente aqui.
    """
    if session.exec(select(Igreja)).first():
        return {"criada": False}

    igreja = Igreja(nome=PADRAO)
    session.add(igreja)
    session.commit()
    session.refresh(igreja)

    vinculadas = 0
    for pessoa in session.exec(select(PessoaICM)).all():
        if pessoa.igreja_id is None:
            pessoa.igreja_id = int(igreja.id or 0)
            session.add(pessoa)
            vinculadas += 1
    session.commit()

    return {"criada": True, "igreja": PADRAO, "vidas_vinculadas": vinculadas}


def total_vidas(session: Session, igreja_id: int) -> int:
    return len(
        session.exec(
            select(PessoaICM).where(PessoaICM.igreja_id == igreja_id)
        ).all()
    )
