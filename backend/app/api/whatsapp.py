"""Rotas do WhatsApp do usuário logado (instância, QR, grupos e contatos)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..deps import usuario_atual
from ..models import User
from ..services import cache, evolution

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


def _detalhes(instancia: str) -> dict:
    resumo = evolution.resumo_instancias()
    dados = resumo.get(instancia) or {}
    return {
        "estado": dados.get("estado") or evolution.estado(instancia),
        "perfil": dados.get("perfil", ""),
        "numero": dados.get("numero", ""),
        "jid": dados.get("jid", ""),
    }


@router.get("/estado")
def estado(user: User = Depends(usuario_atual)) -> dict:
    return {"instancia": user.instancia, **_detalhes(user.instancia)}


@router.post("/conectar")
def conectar(user: User = Depends(usuario_atual)) -> dict:
    instancia = user.instancia
    situacao = evolution.estado(instancia)

    if situacao == "sem_chave":
        raise HTTPException(
            status_code=400,
            detail=(
                "Sem chave da Evolution API. Configure `EVOLUTION_GLOBAL_APIKEY` "
                "no `.env` do backend."
            ),
        )

    if situacao == "nao_existe":
        criou, retorno = evolution.criar_instancia(instancia)
        if not criou:
            raise HTTPException(status_code=400, detail=str(retorno))

        qr, codigo = evolution.extrair_qr(retorno if isinstance(retorno, dict) else None)
        if qr:
            return {
                "instancia": instancia,
                "estado": "connecting",
                "qr": evolution.qr_data_url(qr),
                "codigo": codigo,
                **_detalhes(instancia),
            }

    ok, retorno = evolution.conectar(instancia)
    if not ok:
        raise HTTPException(status_code=400, detail=str(retorno))

    qr, codigo = evolution.extrair_qr(retorno if isinstance(retorno, dict) else None)
    return {
        "instancia": instancia,
        "estado": evolution.estado(instancia),
        "qr": evolution.qr_data_url(qr),
        "codigo": codigo,
        **_detalhes(instancia),
    }


@router.get("/qr")
def qr(user: User = Depends(usuario_atual)) -> dict:
    ok, retorno = evolution.conectar(user.instancia)
    if not ok:
        raise HTTPException(status_code=400, detail=str(retorno))

    qr_valor, codigo = evolution.extrair_qr(
        retorno if isinstance(retorno, dict) else None
    )
    return {
        "instancia": user.instancia,
        "estado": evolution.estado(user.instancia),
        "qr": evolution.qr_data_url(qr_valor),
        "codigo": codigo,
    }


@router.post("/desconectar")
def desconectar(user: User = Depends(usuario_atual)) -> dict:
    ok, mensagem = evolution.desconectar(user.instancia)
    if not ok:
        raise HTTPException(status_code=400, detail=mensagem)
    return {"ok": True, "mensagem": mensagem}


@router.get("/grupos")
def grupos(user: User = Depends(usuario_atual)) -> dict:
    chave = cache.chave("grupos", user.instancia)
    dados, salvo_em = cache.ler(chave)

    if dados is None:
        cache.sincronizar(chave, lambda: evolution.buscar_grupos(user.instancia))

    itens = [{"nome": nome, "jid": jid} for nome, jid in (dados or {}).items()]
    return {
        "total": len(itens),
        "grupos": itens,
        "sincronizando": cache.sincronizando(chave),
        "erro": cache.erro(chave),
        "atualizado_em": salvo_em,
    }


@router.post("/grupos/sincronizar")
def sincronizar_grupos(user: User = Depends(usuario_atual)) -> dict:
    chave = cache.chave("grupos", user.instancia)
    cache.sincronizar(
        chave,
        lambda: evolution.buscar_grupos(user.instancia),
        forcar=True,
    )
    return {"sincronizando": cache.sincronizando(chave)}


@router.get("/contatos")
def contatos(user: User = Depends(usuario_atual)) -> dict:
    chave = cache.chave("contatos", user.instancia)
    dados, salvo_em = cache.ler(chave)

    if dados is None:
        cache.sincronizar(chave, lambda: evolution.buscar_contatos(user.instancia))

    itens = [
        {"jid": jid, "nome": nome, "numero": evolution.formatar_numero(jid)}
        for jid, nome in (dados or {}).items()
    ]
    return {
        "total": len(itens),
        "contatos": itens,
        "sincronizando": cache.sincronizando(chave),
        "erro": cache.erro(chave),
        "atualizado_em": salvo_em,
    }


@router.post("/contatos/sincronizar")
def sincronizar_contatos(user: User = Depends(usuario_atual)) -> dict:
    chave = cache.chave("contatos", user.instancia)
    cache.sincronizar(
        chave,
        lambda: evolution.buscar_contatos(user.instancia),
        forcar=True,
    )
    return {"sincronizando": cache.sincronizando(chave)}
