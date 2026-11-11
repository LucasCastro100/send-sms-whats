"""Rotas de usuários: listagem, cadastro e edição — só admin."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..deps import admin_atual
from ..models import User
from ..security import hash_senha
from ..services import evolution
from ..services import grupos as servico_grupos

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])


class UsuarioLista(BaseModel):
    id: int
    nome: str
    usuario: str
    instancia: str
    admin: bool
    funcao: str
    ativo: bool
    grupo_id: Optional[int] = None
    grupo_nome: str = ""
    criado_em: str
    whatsapp: dict


class UsuarioCriar(BaseModel):
    nome: str = Field(min_length=2, max_length=80)
    usuario: str = Field(
        min_length=3, max_length=120, pattern=r"^[a-zA-Z0-9._@-]+$"
    )
    senha: str = Field(min_length=6, max_length=128)
    funcao: str = "lider"
    grupo_id: Optional[int] = None


class UsuarioPatch(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=2, max_length=80)
    funcao: Optional[str] = None
    grupo_id: Optional[int] = None
    senha: Optional[str] = Field(default=None, min_length=6, max_length=128)
    admin: Optional[bool] = None
    ativo: Optional[bool] = None


def _status_whatsapp(resumo: dict, instancia: str) -> dict:
    dados = resumo.get(instancia)
    if not dados:
        return {"estado": "nao_existe", "perfil": "", "numero": "", "jid": ""}
    return dados


def _validar_funcao(valor: str) -> str:
    funcao = str(valor or "").strip().lower()
    if funcao not in servico_grupos.FUNCOES:
        raise HTTPException(
            status_code=400,
            detail="Função inválida. Use `admin`, `lider` ou `frente`.",
        )
    return funcao


def _validar_grupo(session: Session, grupo_id: Optional[int]) -> Optional[int]:
    if not grupo_id:
        return None
    if not servico_grupos.buscar(session, grupo_id):
        raise HTTPException(status_code=400, detail="Grupo de assistência inválido.")
    return grupo_id


def _saida(user: User, session: Session, resumo: dict) -> UsuarioLista:
    return UsuarioLista(
        id=int(user.id or 0),
        nome=user.nome,
        usuario=user.usuario,
        instancia=user.instancia,
        admin=user.admin,
        funcao=servico_grupos.funcao_do_usuario(user),
        ativo=user.ativo,
        grupo_id=user.grupo_id,
        grupo_nome=servico_grupos.nome_do_usuario(session, user),
        criado_em=user.criado_em.strftime("%d/%m/%Y %H:%M"),
        whatsapp=_status_whatsapp(resumo, user.instancia),
    )


@router.get("", response_model=list[UsuarioLista])
def listar(
    session: Session = Depends(get_session),
    _: User = Depends(admin_atual),
) -> list[UsuarioLista]:
    resumo = evolution.resumo_instancias()
    usuarios = session.exec(select(User).order_by(User.nome)).all()
    return [_saida(user, session, resumo) for user in usuarios]


@router.post("", response_model=UsuarioLista, status_code=201)
def criar(
    dados: UsuarioCriar,
    session: Session = Depends(get_session),
    _: User = Depends(admin_atual),
) -> UsuarioLista:
    usuario = dados.usuario.strip().lower()
    if session.exec(select(User).where(User.usuario == usuario)).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esse usuário já existe.",
        )

    funcao = _validar_funcao(dados.funcao)
    grupo_id = _validar_grupo(session, dados.grupo_id)

    user = User(
        nome=dados.nome.strip(),
        usuario=usuario,
        senha_hash=hash_senha(dados.senha),
        instancia=evolution.nome_instancia(usuario),
        admin=funcao == "admin",
        funcao=funcao,
        grupo_id=grupo_id,
        ativo=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return _saida(user, session, evolution.resumo_instancias())


@router.get("/{usuario_id}/whatsapp")
def whatsapp_do_usuario(
    usuario_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(admin_atual),
) -> dict:
    user = session.get(User, usuario_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    resumo = evolution.resumo_instancias()
    dados = _status_whatsapp(resumo, user.instancia)
    return {"instancia": user.instancia, **dados}


@router.patch("/{usuario_id}", response_model=UsuarioLista)
def editar(
    usuario_id: int,
    dados: UsuarioPatch,
    session: Session = Depends(get_session),
    admin: User = Depends(admin_atual),
) -> UsuarioLista:
    user = session.get(User, usuario_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    if user.id == admin.id:
        if dados.ativo is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Você não pode desativar a si mesmo.",
            )
        if dados.admin is False or (
            dados.funcao is not None and dados.funcao.strip().lower() != "admin"
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Você não pode remover o seu próprio admin.",
            )

    if dados.nome is not None:
        user.nome = dados.nome.strip()

    if dados.funcao is not None:
        funcao = _validar_funcao(dados.funcao)
        user.funcao = funcao
        user.admin = funcao == "admin"

    if dados.admin is not None:
        user.admin = dados.admin
        if dados.admin:
            user.funcao = "admin"
        elif user.funcao == "admin":
            user.funcao = "lider"

    if "grupo_id" in dados.model_fields_set:
        user.grupo_id = _validar_grupo(session, dados.grupo_id)

    if dados.senha is not None:
        user.senha_hash = hash_senha(dados.senha)

    if dados.ativo is not None:
        user.ativo = dados.ativo

    session.add(user)
    session.commit()
    session.refresh(user)

    return _saida(user, session, evolution.resumo_instancias())
