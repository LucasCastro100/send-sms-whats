"""Cria os usuários iniciais a partir do APP_USERS (ou do admin padrão)."""

from __future__ import annotations

import json

from sqlmodel import Session, select

from .config import settings
from .db import engine
from .models import User
from .security import hash_senha
from .services import evolution


def _usuarios_iniciais() -> dict:
    if settings.app_users.strip():
        try:
            dados = json.loads(settings.app_users)
        except json.JSONDecodeError:
            dados = {}
        if isinstance(dados, dict) and dados:
            return dados

    return {
        settings.admin_usuario: {
            "senha": settings.admin_senha,
            "nome": settings.admin_nome,
            "admin": True,
        }
    }


def semear() -> None:
    with Session(engine) as session:
        if session.exec(select(User)).first():
            return

        for usuario, dados in _usuarios_iniciais().items():
            if not isinstance(dados, dict):
                continue

            nome = str(dados.get("nome") or usuario).strip()
            instancia = str(
                dados.get("instancia") or evolution.nome_instancia(usuario)
            ).strip()
            senha = str(dados.get("senha") or settings.admin_senha)

            session.add(
                User(
                    nome=nome,
                    usuario=str(usuario).strip().lower(),
                    senha_hash=hash_senha(senha),
                    instancia=instancia,
                    admin=bool(dados.get("admin")),
                    funcao="admin" if dados.get("admin") else "lider",
                    ativo=True,
                )
            )

        session.commit()
