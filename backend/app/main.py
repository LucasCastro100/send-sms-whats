"""Aplicação FastAPI do Check Birthday."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from .api import (
    aniversariantes,
    auth,
    dashboard,
    eventos,
    grupos,
    igrejas,
    importacao,
    mensagens,
    observacoes,
    oracoes,
    pessoas,
    presenca,
    users,
    whatsapp,
)
from .config import settings
from .db import engine, init_db
from .seed import semear
from .services import agendador, disparo_automatico
from .services import grupos as servico_grupos
from .services import igrejas as servico_igrejas
from .services.migracao import migrar_arquivos, separar_tabelas_antigas


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    semear()
    with Session(engine) as session:
        # Antes: uma tabela `pessoas` com coluna `fonte`. Agora: `icm` e `zoom`.
        separar_tabelas_antigas(session)
        # Primeiro start: leva data.pdf/CSV/JSON antigos para as tabelas.
        migrar_arquivos(session)
        # Grupos de assistência vêm da coluna `grupo` da tabela `icm`.
        servico_grupos.sincronizar(session)
        # Primeiro start: cria a igreja padrão e vincula as vidas do ICM a ela.
        servico_igrejas.garantir_padrao(session)

    # Envios agendados e o disparo diário dos aniversariantes do ICM.
    agendador.iniciar()
    disparo_automatico.iniciar()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.lista_cors(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(grupos.router)
app.include_router(igrejas.router)
app.include_router(whatsapp.router)
app.include_router(dashboard.router)
app.include_router(pessoas.router)
app.include_router(importacao.router)
app.include_router(aniversariantes.router)
app.include_router(mensagens.router)
app.include_router(presenca.router)
app.include_router(oracoes.router)
app.include_router(eventos.router)
app.include_router(observacoes.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "app": settings.app_name}
