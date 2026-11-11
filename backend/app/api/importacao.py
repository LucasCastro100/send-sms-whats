"""Importação de PDF/planilha: pré-visualização e confirmação."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..deps import admin_atual
from ..models import Igreja, Importacao, User
from ..services import importacao as servico_importacao
from ..services import pessoas as servico_pessoas

router = APIRouter(prefix="/api/importar", tags=["importar"])

TAMANHO_MAXIMO = 20 * 1024 * 1024  # 20 MB
ID_VALIDO = re.compile(r"^[a-f0-9]{32}$")


def _pasta_uploads() -> Path:
    pasta = Path(settings.uploads_dir)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _pasta_upload(upload_id: str) -> Path:
    if not ID_VALIDO.match(upload_id):
        raise HTTPException(status_code=400, detail="Identificador inválido.")
    return _pasta_uploads() / upload_id


def _ler_meta(upload_id: str) -> dict:
    pasta = _pasta_upload(upload_id)
    meta = pasta / "meta.json"
    if not meta.exists():
        raise HTTPException(
            status_code=404,
            detail="Análise não encontrada. Envie o arquivo de novo.",
        )
    try:
        return json.loads(meta.read_text("utf-8"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Análise corrompida.")


@router.post("/preview")
async def preview(
    arquivo: UploadFile = File(...),
    fonte: str = Form(...),
    mapeamento: str = Form(""),
    igreja_id: Optional[int] = Form(None),
    session: Session = Depends(get_session),
    _: User = Depends(admin_atual),
) -> dict:
    fonte = fonte.strip().lower()
    if fonte not in servico_pessoas.FONTES:
        raise HTTPException(
            status_code=400, detail="Fonte inválida. Use `icm` ou `zoom`."
        )
    if igreja_id is not None:
        if fonte != "icm":
            raise HTTPException(
                status_code=400,
                detail="O vínculo com igreja vale apenas para a lista ICM.",
            )
        if not session.get(Igreja, igreja_id):
            raise HTTPException(status_code=400, detail="Igreja não encontrada.")

    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if len(conteudo) > TAMANHO_MAXIMO:
        raise HTTPException(status_code=400, detail="Arquivo maior que 20 MB.")

    mapa = None
    if mapeamento.strip():
        try:
            mapa = json.loads(mapeamento)
        except ValueError:
            raise HTTPException(status_code=400, detail="Mapeamento inválido.")
        if not isinstance(mapa, dict):
            raise HTTPException(status_code=400, detail="Mapeamento inválido.")

    nome = arquivo.filename or "arquivo"
    try:
        linhas, mapa_usado, avisos = servico_importacao.ler_arquivo(
            nome, conteudo, mapa
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not linhas:
        raise HTTPException(
            status_code=400,
            detail=avisos[0] if avisos else "Nenhuma pessoa encontrada no arquivo.",
        )

    diff = servico_importacao.analisar(session, fonte, linhas)

    upload_id = uuid.uuid4().hex
    pasta = _pasta_upload(upload_id)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"arquivo{Path(nome).suffix.lower()}").write_bytes(conteudo)
    (pasta / "meta.json").write_text(
        json.dumps(
            {
                "arquivo": nome,
                "formato": Path(nome).suffix.lower().lstrip("."),
                "fonte": fonte,
                "igreja_id": igreja_id,
                "mapeamento": mapa_usado,
                "linhas": linhas,
                "avisos": avisos,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return {
        "upload_id": upload_id,
        "arquivo": nome,
        "formato": Path(nome).suffix.lower().lstrip("."),
        "fonte": fonte,
        "mapeamento": mapa_usado,
        "avisos": avisos,
        **diff,
    }


@router.post("/{upload_id}/confirmar")
def confirmar(
    upload_id: str,
    session: Session = Depends(get_session),
    user: User = Depends(admin_atual),
) -> dict:
    meta = _ler_meta(upload_id)

    resultado = servico_importacao.aplicar(
        session,
        fonte=meta["fonte"],
        linhas=meta["linhas"],
        arquivo=meta["arquivo"],
        formato=meta["formato"],
        usuario_id=user.id,
        usuario=user.usuario,
        igreja_id=meta.get("igreja_id"),
    )

    shutil.rmtree(_pasta_upload(upload_id), ignore_errors=True)

    return {
        "arquivo": meta["arquivo"],
        "fonte": meta["fonte"],
        **resultado,
    }


@router.get("/historico")
def historico(
    limite: int = 20,
    session: Session = Depends(get_session),
    _: User = Depends(admin_atual),
) -> dict:
    limite = max(1, min(limite, 100))
    registros = session.exec(
        select(Importacao).order_by(Importacao.criado_em.desc()).limit(limite)
    ).all()

    return {
        "total": len(registros),
        "importacoes": [
            {
                "id": int(registro.id or 0),
                "arquivo": registro.arquivo,
                "formato": registro.formato,
                "fonte": registro.fonte,
                "usuario": registro.usuario,
                "inseridos": registro.inseridos,
                "atualizados": registro.atualizados,
                "iguais": registro.iguais,
                "ausentes": registro.ausentes,
                "conflitos": registro.conflitos,
                "criado_em": registro.criado_em.strftime("%d/%m/%Y %H:%M"),
            }
            for registro in registros
        ],
    }
