"""Consulta e edição das pessoas (aniversariantes) já no banco."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from ..db import get_session
from ..deps import usuario_atual
from ..models import Igreja, PessoaBase, User
from ..services import grupos as servico_grupos
from ..services import igrejas as servico_igrejas
from ..services import pessoas as servico_pessoas

router = APIRouter(prefix="/api/pessoas", tags=["pessoas"])


class PessoaOut(BaseModel):
    id: int
    fonte: str
    nome: str
    nome_chave: str
    dia: Optional[int]
    mes: Optional[int]
    ano: Optional[int]
    data: str
    mes_nome: str
    idade: Optional[int]
    grupo: str
    telefone: str
    tel_residencial: str
    tel_comercial: str
    celular: str
    situacao: str
    categoria: str
    genero: Optional[str]
    excluido: bool
    ativo: bool
    igreja_id: Optional[int]
    igreja_nome: str
    visto_em: Optional[str]
    ultima_visita: Optional[str]
    dias_sem_visita: Optional[int]


class PessoaPatch(BaseModel):
    # Cada fonte tem a sua tabela; a fonte diz em qual delas procurar o id.
    fonte: Optional[str] = None
    genero: Optional[str] = None
    excluido: Optional[bool] = None
    ativo: Optional[bool] = None
    telefone: Optional[str] = None
    grupo: Optional[str] = None
    # `null` desvincula; só a lista ICM tem igreja.
    igreja_id: Optional[int] = None


def saida(
    pessoa: PessoaBase, igrejas: Optional[dict[int, str]] = None
) -> PessoaOut:
    igreja_id = getattr(pessoa, "igreja_id", None)
    return PessoaOut(
        id=int(pessoa.id or 0),
        fonte=pessoa.fonte,
        nome=pessoa.nome,
        nome_chave=pessoa.nome_chave,
        dia=pessoa.dia,
        mes=pessoa.mes,
        ano=pessoa.ano,
        data=servico_pessoas.formatar_data(pessoa.dia, pessoa.mes),
        mes_nome=servico_pessoas.nome_mes(pessoa.mes),
        idade=servico_pessoas.idade(pessoa),
        grupo=pessoa.grupo,
        telefone=pessoa.telefone,
        tel_residencial=pessoa.tel_residencial,
        tel_comercial=pessoa.tel_comercial,
        celular=pessoa.celular,
        situacao=pessoa.situacao,
        categoria=pessoa.categoria,
        genero=pessoa.genero,
        excluido=pessoa.excluido,
        ativo=pessoa.ativo,
        igreja_id=igreja_id,
        igreja_nome=(igrejas or {}).get(igreja_id, "") if igreja_id else "",
        visto_em=pessoa.visto_em.strftime("%d/%m/%Y") if pessoa.visto_em else None,
        ultima_visita=(
            pessoa.ultima_visita.strftime("%d/%m/%Y") if pessoa.ultima_visita else None
        ),
        dias_sem_visita=servico_pessoas.dias_sem_visita(pessoa),
    )


def _localizar(
    session: Session,
    pessoa_id: int,
    fonte: Optional[str],
    user: User,
) -> Optional[PessoaBase]:
    """Busca pelo id na tabela da fonte; sem fonte, tenta as duas.

    A busca respeita as fontes que o usuário pode ver (Zoom é só do admin).
    """
    permitidas = servico_pessoas.fontes_do_usuario(user)

    if fonte:
        if fonte.lower() not in servico_pessoas.FONTES:
            raise HTTPException(status_code=400, detail="Fonte inválida.")
        if fonte.lower() not in permitidas:
            raise HTTPException(
                status_code=403,
                detail="A lista do Zoom é restrita ao administrador.",
            )
        pessoa = session.get(servico_pessoas.modelo(fonte), pessoa_id)
    else:
        encontradas = [
            pessoa
            for pessoa in (
                session.get(servico_pessoas.modelo(nome), pessoa_id)
                for nome in permitidas
            )
            if pessoa
        ]
        if len(encontradas) > 1:
            raise HTTPException(
                status_code=409,
                detail="Esse id existe nas duas tabelas. Informe a fonte.",
            )
        pessoa = encontradas[0] if encontradas else None

    # A ficha da vida do ICM respeita o grupo/frente do usuário.
    if pessoa and pessoa.fonte == "icm":
        if pessoa.nome_chave not in servico_grupos.chaves_do_escopo(session, user):
            raise HTTPException(
                status_code=403, detail="Você não tem acesso a esta vida."
            )
    return pessoa


@router.get("", response_model=list[PessoaOut])
def listar(
    fonte: Optional[str] = None,
    busca: Optional[str] = None,
    incluir_inativos: bool = False,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> list[PessoaOut]:
    permitidas = servico_pessoas.fontes_do_usuario(user)
    if fonte:
        fonte = fonte.lower()
        if fonte not in servico_pessoas.FONTES:
            raise HTTPException(status_code=400, detail="Fonte inválida.")
        if fonte not in permitidas:
            raise HTTPException(
                status_code=403,
                detail="A lista do Zoom é restrita ao administrador.",
            )
    elif len(permitidas) == 1:
        # Sem filtro explícito, o não-admin só enxerga a própria lista.
        fonte = permitidas[0]

    escopo = servico_grupos.escopo(session, user)
    igrejas = servico_igrejas.mapa(session)

    return [
        saida(pessoa, igrejas)
        for pessoa in servico_pessoas.listar(
            session,
            fonte=fonte,
            busca=busca,
            incluir_inativos=incluir_inativos,
            grupos=escopo["grupos"],
            apenas_mulheres=escopo["apenas_mulheres"],
        )
    ]


@router.get("/resumo")
def resumo(
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    return servico_pessoas.contar_por_fonte(
        session, servico_pessoas.fontes_do_usuario(user)
    )


@router.patch("/{pessoa_id}", response_model=PessoaOut)
def editar(
    pessoa_id: int,
    dados: PessoaPatch,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> PessoaOut:
    pessoa = _localizar(session, pessoa_id, dados.fonte, user)
    if not pessoa:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada.")

    if dados.genero is not None:
        genero = dados.genero.strip().upper()[:1]
        if genero not in ("", "M", "F"):
            raise HTTPException(
                status_code=400, detail="Gênero deve ser `M`, `F` ou vazio."
            )
        pessoa.genero = genero or None

    if dados.excluido is not None:
        pessoa.excluido = dados.excluido
    if dados.ativo is not None:
        pessoa.ativo = dados.ativo
    if dados.telefone is not None:
        pessoa.telefone = servico_pessoas.normalizar_telefone(dados.telefone)
    if dados.grupo is not None:
        pessoa.grupo = dados.grupo.strip()

    # Igreja: o campo foi enviado? (null desvincula a vida da igreja).
    if "igreja_id" in dados.model_fields_set:
        if pessoa.fonte != "icm":
            raise HTTPException(
                status_code=400,
                detail="O vínculo com igreja vale apenas para a lista ICM.",
            )
        if dados.igreja_id is not None and not session.get(Igreja, dados.igreja_id):
            raise HTTPException(status_code=400, detail="Igreja não encontrada.")
        pessoa.igreja_id = dados.igreja_id

    pessoa.atualizado_em = datetime.utcnow()
    session.add(pessoa)
    session.commit()
    session.refresh(pessoa)

    # O disparo do GitHub Actions lê os JSON de `data/`, não o banco: mantém o
    # espelho igual ao painel para a mensagem sair com os ajustes daqui.
    if dados.excluido is not None:
        servico_pessoas.sincronizar_exclusao(
            pessoa.nome_chave, pessoa.fonte, bool(pessoa.excluido)
        )
    if dados.genero is not None:
        servico_pessoas.sincronizar_genero(
            pessoa.nome_chave, pessoa.fonte, pessoa.genero
        )

    return saida(pessoa, servico_igrejas.mapa(session))


@router.get("/{pessoa_id}", response_model=PessoaOut)
def detalhe(
    pessoa_id: int,
    fonte: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> PessoaOut:
    pessoa = _localizar(session, pessoa_id, fonte, user)
    if not pessoa:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada.")
    return saida(pessoa, servico_igrejas.mapa(session))


class VisitaIn(BaseModel):
    fonte: Optional[str] = None


@router.post("/{pessoa_id}/visita", response_model=PessoaOut)
def registrar_visita(
    pessoa_id: int,
    dados: VisitaIn,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> PessoaOut:
    """Marca a visita de hoje: zera o contador e a pessoa sai da frente da fila."""
    pessoa = _localizar(session, pessoa_id, dados.fonte, user)
    if not pessoa:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada.")

    hoje = date.today()
    pessoa.ultima_visita = hoje
    pessoa.dias_sem_visita = 0
    pessoa.visitas_referencia = hoje
    pessoa.atualizado_em = datetime.utcnow()

    session.add(pessoa)
    session.commit()
    session.refresh(pessoa)
    return saida(pessoa, servico_igrejas.mapa(session))
