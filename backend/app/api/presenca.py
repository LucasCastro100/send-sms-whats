"""Controle de presença: faltas do dia, números, avisos e relatórios."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..db import get_session
from ..deps import usuario_atual
from ..models import Igreja, PessoaICM, PresencaDia, User, Visita
from ..services import cache, evolution, horarios
from ..services import grupos as servico_grupos
from ..services import igrejas as servico_igrejas
from ..services import pessoas as servico_pessoas
from ..services import presenca as servico_presenca

router = APIRouter(prefix="/api/presenca", tags=["presenca"])

LIMITE_TEXTO = 4000


class RegistroEntrada(BaseModel):
    dia: str
    # culto | escola_biblica
    tipo: str = "culto"
    nomes_chave: List[str] = []


class FaltasEntrada(BaseModel):
    dia: str
    tipo: str = "culto"
    nomes_chave: List[str] = []


class EnvioEntrada(BaseModel):
    dia: str
    # falta | visita
    tipo: str
    # culto | escola_biblica (qual lançamento o aviso se refere)
    tipo_presenca: str = "culto"
    nomes_chave: Optional[List[str]] = None


class NumeroEntrada(BaseModel):
    nome_chave: str
    nome: str = ""
    jid: str = ""


class MensagensEntrada(BaseModel):
    falta: str
    visita: str


# ---------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------
def _validar_dia(dia: str) -> str:
    dia = str(dia or "").strip()
    if not servico_presenca.dia_valido(dia):
        raise HTTPException(status_code=400, detail="Data inválida. Use AAAA-MM-DD.")
    return dia


def _hoje() -> str:
    return horarios.agora_brasilia().strftime("%Y-%m-%d")


def _numero(pessoa, contatos: Dict[str, object]) -> str:
    contato = contatos.get(pessoa.nome_chave)
    jid = getattr(contato, "jid", "") if contato else ""
    return str(jid or pessoa.telefone or "").strip()


def _pessoas_do_escopo(session: Session, user: User) -> list:
    escopo = servico_grupos.escopo(session, user)
    return servico_pessoas.listar(
        session,
        fonte="icm",
        grupos=escopo["grupos"],
        apenas_mulheres=escopo["apenas_mulheres"],
    )


def _estado(session: Session, dia: str, tipo: str, user: User) -> dict:
    tipo = servico_presenca.normalizar_tipo(tipo)
    pessoas = _pessoas_do_escopo(session, user)
    dias_tipo = servico_presenca.carregar_dias(session, tipo)
    dias_todos = servico_presenca.carregar_dias(session)
    faltas = dias_tipo.get(dia, set())
    conferido = dia in dias_tipo
    participantes_dia = (
        servico_presenca.participantes_do_dia(session, dia, tipo)
        if tipo == "escola_biblica"
        else set()
    )
    contatos = servico_presenca.contatos(session)
    visitas = {
        visita.nome_chave: visita
        for visita in session.exec(select(Visita)).all()
    }
    mensagens = servico_presenca.carregar_mensagens(session)
    grupos = servico_grupos.mapa(session)
    igrejas = {
        int(igreja.id or 0): igreja
        for igreja in session.exec(select(Igreja)).all()
    }

    itens = []
    for pessoa in pessoas:
        chave = pessoa.nome_chave
        numero = _numero(pessoa, contatos)
        falta = chave in faltas
        participou = chave in participantes_dia
        presente = participou if tipo == "escola_biblica" else (conferido and not falta)
        consecutivas = servico_presenca.faltas_consecutivas(chave, dia, dias_todos)
        # Só quem faltou hoje pode ter visita pendente.
        if falta:
            precisa, _ = servico_presenca.precisa_visita(
                session, chave, dia, dias_todos, visitas=visitas
            )
        else:
            precisa = False

        grupo = grupos.get(pessoa.grupo)
        igreja = igrejas.get(getattr(pessoa, "igreja_id", None) or 0)
        itens.append(
            {
                "id": int(pessoa.id or 0),
                "nome": pessoa.nome,
                "nome_chave": chave,
                "grupo": pessoa.grupo,
                "igreja_id": getattr(pessoa, "igreja_id", None),
                "igreja_nome": igreja.nome if igreja else "",
                "telefone": pessoa.telefone,
                "numero": numero,
                "numero_formatado": evolution.formatar_numero(numero) if numero else "",
                "vinculado": bool(numero),
                "falta": falta,
                "presente": bool(presente),
                "participou": bool(participou),
                "faltas_consecutivas": consecutivas,
                "precisa_visita": precisa,
                "contato_grupo": bool(
                    grupo and grupo.responsavel_whatsapp
                ),
                "contato_igreja": bool(
                    igreja and igreja.pastor_whatsapp
                ),
            }
        )

    itens.sort(key=lambda item: item["nome_chave"])
    faltantes = [item for item in itens if item["falta"]]
    visitas_pendentes = [item for item in itens if item["precisa_visita"]]
    participantes = [item for item in itens if item["participou"]]

    historico = []
    for registro in sorted(dias_tipo, reverse=True)[:30]:
        historico.append(
            {
                "dia": registro,
                "data": servico_presenca.data_br(registro),
                "faltantes": len(dias_tipo.get(registro, set())),
                "participantes": (
                    len(servico_presenca.participantes_do_dia(session, registro, tipo))
                    if tipo == "escola_biblica"
                    else 0
                ),
            }
        )

    return {
        "dia": dia,
        "data": servico_presenca.data_br(dia),
        "tipo": tipo,
        "tipo_rotulo": servico_presenca.rotulo_tipo(tipo),
        "conferido": conferido,
        "limite_visita": servico_presenca.LIMITE_VISITA,
        "mensagens": mensagens,
        "grupos": sorted({item["grupo"] for item in itens if item["grupo"]}),
        "total": len(itens),
        "presentes": sum(1 for item in itens if item["presente"]),
        "faltantes": len(faltantes),
        "participantes": len(participantes),
        "com_numero": sum(1 for item in itens if item["vinculado"]),
        "sem_numero": sum(1 for item in itens if not item["vinculado"]),
        "visitas_pendentes": len(visitas_pendentes),
        "pessoas": itens,
        "historico": historico,
    }


# ---------------------------------------------------------------------------
# Faltas / participantes do dia
# ---------------------------------------------------------------------------
@router.get("")
def estado(
    dia: Optional[str] = None,
    tipo: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    return _estado(
        session,
        _validar_dia(dia or _hoje()),
        servico_presenca.normalizar_tipo(tipo),
        user,
    )


@router.post("/registrar")
def registrar(
    dados: RegistroEntrada,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    dia = _validar_dia(dados.dia)
    tipo = servico_presenca.normalizar_tipo(dados.tipo)
    pessoas = _pessoas_do_escopo(session, user)
    permitidas = {pessoa.nome_chave for pessoa in pessoas}

    chaves = [
        servico_pessoas.normalizar_nome(nome)
        for nome in dados.nomes_chave
        if str(nome).strip()
    ]
    # Ninguém lança presença para quem está fora do escopo dele.
    chaves = [chave for chave in chaves if chave in permitidas]

    total = servico_presenca.salvar_presenca(
        session,
        dia,
        tipo,
        chaves,
        elenco=[(pessoa.nome, pessoa.nome_chave) for pessoa in pessoas],
    )

    estado_atual = _estado(session, dia, tipo, user)
    estado_atual["salvos"] = total
    return estado_atual


@router.post("/faltas")
def salvar_faltas(
    dados: FaltasEntrada,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    """Compatibilidade com a tela antiga: salva faltas do culto."""
    return registrar(
        RegistroEntrada(
            dia=dados.dia,
            tipo=dados.tipo or "culto",
            nomes_chave=dados.nomes_chave,
        ),
        session,
        user,
    )


# ---------------------------------------------------------------------------
# Envio dos avisos (responsável do grupo + pastor da igreja)
# ---------------------------------------------------------------------------
@router.post("/enviar")
def enviar(
    dados: EnvioEntrada,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    dia = _validar_dia(dados.dia)
    tipo = (dados.tipo or "").strip().lower()
    if tipo not in servico_presenca.CHAVES_MENSAGEM:
        raise HTTPException(status_code=400, detail="Tipo deve ser `falta` ou `visita`.")
    tipo_presenca = servico_presenca.normalizar_tipo(dados.tipo_presenca)

    pessoas = _pessoas_do_escopo(session, user)
    por_chave = {pessoa.nome_chave: pessoa for pessoa in pessoas}

    if tipo == "falta":
        if dados.nomes_chave:
            alvos = {
                servico_pessoas.normalizar_nome(nome)
                for nome in dados.nomes_chave
                if str(nome).strip()
            }
        else:
            alvos = servico_presenca.faltas_do_dia(session, dia, tipo_presenca)
    else:
        dias = servico_presenca.carregar_dias(session)
        visitas = {
            visita.nome_chave: visita
            for visita in session.exec(select(Visita)).all()
        }
        if dados.nomes_chave:
            candidatos = {
                servico_pessoas.normalizar_nome(nome)
                for nome in dados.nomes_chave
                if str(nome).strip()
            }
        else:
            candidatos = set(por_chave)
        alvos = {
            chave
            for chave in candidatos
            if servico_presenca.precisa_visita(
                session, chave, dia, dias, visitas=visitas
            )[0]
        }

    # Ninguém envia para quem está fora do escopo dele.
    alvos &= set(por_chave)

    if not alvos:
        raise HTTPException(
            status_code=400,
            detail=(
                "Nenhuma vida para avisar nesse dia."
                if tipo == "falta"
                else "Ninguém atingiu o limite de faltas seguidas."
            ),
        )

    mensagens = servico_presenca.carregar_mensagens(session)
    modelo = mensagens[tipo]
    grupos = servico_grupos.mapa(session)
    igrejas = {
        int(igreja.id or 0): igreja
        for igreja in session.exec(select(Igreja)).all()
    }
    dias = servico_presenca.carregar_dias(session)

    por_grupo: Dict[str, List] = {}
    por_igreja: Dict[int, List] = {}
    for chave in sorted(alvos):
        pessoa = por_chave[chave]
        if pessoa.grupo:
            por_grupo.setdefault(pessoa.grupo, []).append(pessoa)
        igreja_id = getattr(pessoa, "igreja_id", None)
        if igreja_id:
            por_igreja.setdefault(int(igreja_id), []).append(pessoa)

    resultados = []
    sem_contato = []
    entregues: set[str] = set()

    def enviar_para(
        *,
        destino: str,
        referencia: str,
        responsavel: str,
        numero: str,
        lista: list,
    ) -> None:
        nomes = sorted(pessoa.nome for pessoa in lista)
        chaves = [pessoa.nome_chave for pessoa in lista]
        if not numero:
            sem_contato.append(
                {
                    "destino": destino,
                    "referencia": referencia,
                    "responsavel": responsavel,
                    "nomes": nomes,
                }
            )
            return

        texto = servico_presenca.montar_texto(
            modelo,
            responsavel=responsavel,
            nomes=nomes,
            dia=dia,
            tipo=tipo_presenca,
            limite=servico_presenca.LIMITE_VISITA,
        )
        ok, retorno = evolution.enviar_texto(user.instancia, numero, texto)
        resultados.append(
            {
                "destino": destino,
                "referencia": referencia,
                "responsavel": responsavel,
                "numero": evolution.formatar_numero(numero),
                "ok": ok,
                "mensagem": retorno,
                "nomes": nomes,
                "total": len(nomes),
            }
        )
        if ok:
            entregues.update(chaves)

    for nome_grupo, lista in sorted(por_grupo.items()):
        grupo = grupos.get(nome_grupo)
        enviar_para(
            destino="grupo",
            referencia=nome_grupo,
            responsavel=(
                (grupo.responsavel_nome if grupo else "")
                or f"Responsável do grupo {nome_grupo}"
            ),
            numero=(grupo.responsavel_whatsapp if grupo else ""),
            lista=lista,
        )

    for igreja_id, lista in sorted(por_igreja.items()):
        igreja = igrejas.get(igreja_id)
        enviar_para(
            destino="igreja",
            referencia=(igreja.nome if igreja else f"Igreja {igreja_id}"),
            responsavel=(
                (igreja.pastor_nome if igreja else "")
                or f"Pastor da {igreja.nome if igreja else 'igreja'}"
            ),
            numero=(igreja.pastor_whatsapp if igreja else ""),
            lista=lista,
        )

    if tipo == "visita":
        for chave in sorted(entregues):
            pessoa = por_chave.get(chave)
            if not pessoa:
                continue
            servico_presenca.registrar_visita(
                session,
                pessoa.nome,
                chave,
                dia,
                servico_presenca.faltas_consecutivas(chave, dia, dias),
            )

    enviados = sum(1 for item in resultados if item["ok"])
    return {
        "tipo": tipo,
        "tipo_presenca": tipo_presenca,
        "dia": dia,
        "enviados": enviados,
        "falhas": len(resultados) - enviados,
        "sem_contato": sem_contato,
        "resultados": resultados,
    }


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------
def _intervalo(de: Optional[str], ate: Optional[str]) -> tuple[str, str]:
    ate = _validar_dia(ate or _hoje())
    if de:
        de = _validar_dia(de)
    else:
        de = (
            datetime.strptime(ate, "%Y-%m-%d") - timedelta(days=30)
        ).strftime("%Y-%m-%d")
    if de > ate:
        raise HTTPException(
            status_code=400, detail="A data inicial não pode ser depois da final."
        )
    return de, ate


@router.get("/relatorio")
def relatorio(
    de: Optional[str] = None,
    ate: Optional[str] = None,
    tipo: Optional[str] = None,
    grupo: Optional[str] = None,
    igreja_id: Optional[int] = None,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    de, ate = _intervalo(de, ate)
    tipo_filtro = (tipo or "todos").strip().lower()
    if tipo_filtro not in ("todos", *servico_presenca.TIPOS):
        raise HTTPException(
            status_code=400,
            detail="Tipo deve ser `culto`, `escola_biblica` ou `todos`.",
        )

    pessoas = _pessoas_do_escopo(session, user)
    if grupo:
        pessoas = [pessoa for pessoa in pessoas if pessoa.grupo == grupo]
    if igreja_id:
        pessoas = [
            pessoa
            for pessoa in pessoas
            if getattr(pessoa, "igreja_id", None) == igreja_id
        ]

    nomes_igrejas = servico_igrejas.mapa(session)
    consulta = select(PresencaDia).where(
        PresencaDia.dia >= de, PresencaDia.dia <= ate
    )
    if tipo_filtro != "todos":
        consulta = consulta.where(PresencaDia.tipo == tipo_filtro)
    registros = list(
        session.exec(consulta.order_by(PresencaDia.dia.desc())).all()
    )

    dias_culto = servico_presenca.carregar_dias(session, "culto")
    dias_eb = servico_presenca.carregar_dias(session, "escola_biblica")
    participantes_eb = servico_presenca.carregar_participantes(
        session, "escola_biblica"
    )

    lancamentos = []
    for registro in registros:
        dia = registro.dia
        tipo_dia = servico_presenca.normalizar_tipo(registro.tipo)
        total = len(pessoas)
        if tipo_dia == "escola_biblica":
            presentes = sum(
                1
                for pessoa in pessoas
                if pessoa.nome_chave in participantes_eb.get(dia, set())
            )
        else:
            faltantes = sum(
                1
                for pessoa in pessoas
                if pessoa.nome_chave in dias_culto.get(dia, set())
            )
            presentes = total - faltantes
        faltantes = total - presentes
        lancamentos.append(
            {
                "dia": dia,
                "data": servico_presenca.data_br(dia),
                "tipo": tipo_dia,
                "tipo_rotulo": servico_presenca.rotulo_tipo(tipo_dia),
                "total": total,
                "presentes": presentes,
                "faltantes": faltantes,
                "percentual": round((presentes / total) * 100, 1) if total else 0.0,
            }
        )

    por_pessoa = []
    for pessoa in pessoas:
        chave = pessoa.nome_chave
        presencas = 0
        faltas = 0
        for registro in registros:
            dia = registro.dia
            if servico_presenca.normalizar_tipo(registro.tipo) == "escola_biblica":
                presente = chave in participantes_eb.get(dia, set())
            else:
                presente = chave not in dias_culto.get(dia, set())
            if presente:
                presencas += 1
            else:
                faltas += 1
        total = presencas + faltas
        por_pessoa.append(
            {
                "id": int(pessoa.id or 0),
                "nome": pessoa.nome,
                "nome_chave": chave,
                "grupo": pessoa.grupo,
                "igreja_id": getattr(pessoa, "igreja_id", None),
                "igreja_nome": nomes_igrejas.get(
                    getattr(pessoa, "igreja_id", None), ""
                ),
                "presencas": presencas,
                "faltas": faltas,
                "total": total,
                "percentual": round((presencas / total) * 100, 1) if total else 0.0,
            }
        )

    por_pessoa.sort(key=lambda item: item["nome_chave"])
    total_presentes = sum(item["presentes"] for item in lancamentos)
    total_faltas = sum(item["faltantes"] for item in lancamentos)
    total_geral = total_presentes + total_faltas

    return {
        "de": de,
        "ate": ate,
        "tipo": tipo_filtro,
        "tipo_rotulo": (
            "Culto e Escola Bíblica"
            if tipo_filtro == "todos"
            else servico_presenca.rotulo_tipo(tipo_filtro)
        ),
        "resumo": {
            "lancamentos": len(lancamentos),
            "presentes": total_presentes,
            "faltas": total_faltas,
            "percentual": (
                round((total_presentes / total_geral) * 100, 1)
                if total_geral
                else 0.0
            ),
        },
        "lancamentos": lancamentos,
        "pessoas": por_pessoa,
    }


# ---------------------------------------------------------------------------
# Histórico de uma vida (gráfico da ficha)
# ---------------------------------------------------------------------------
@router.get("/pessoa/{pessoa_id}")
def historico_pessoa(
    pessoa_id: int,
    fonte: str = "icm",
    limite: int = 24,
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    if fonte.lower() != "icm":
        raise HTTPException(
            status_code=400,
            detail="A presença só existe para a lista ICM.",
        )

    pessoa = session.get(PessoaICM, pessoa_id)
    if not pessoa:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada.")

    # A pessoa precisa estar no escopo do usuário.
    permitidas = {
        item.nome_chave for item in _pessoas_do_escopo(session, user)
    }
    if pessoa.nome_chave not in permitidas:
        raise HTTPException(
            status_code=403, detail="Você não tem acesso a esta vida."
        )

    limite = max(1, min(int(limite), 60))
    todos_registros = list(
        session.exec(
            select(PresencaDia).order_by(PresencaDia.dia.desc())
        ).all()
    )
    registros = todos_registros[:limite]

    dias_culto = servico_presenca.carregar_dias(session, "culto")
    participantes_eb = servico_presenca.carregar_participantes(
        session, "escola_biblica"
    )

    eventos = []
    resumo = {
        "culto": {"total": 0, "presencas": 0, "faltas": 0, "percentual": 0.0},
        "escola_biblica": {
            "total": 0,
            "presencas": 0,
            "faltas": 0,
            "percentual": 0.0,
        },
        "geral": {"total": 0, "presencas": 0, "faltas": 0, "percentual": 0.0},
    }
    for registro in registros:
        tipo_dia = servico_presenca.normalizar_tipo(registro.tipo)
        dia = registro.dia
        if tipo_dia == "escola_biblica":
            presente = pessoa.nome_chave in participantes_eb.get(dia, set())
        else:
            presente = pessoa.nome_chave not in dias_culto.get(dia, set())

        eventos.append(
            {
                "dia": dia,
                "data": servico_presenca.data_br(dia),
                "tipo": tipo_dia,
                "tipo_rotulo": servico_presenca.rotulo_tipo(tipo_dia),
                "presente": presente,
                "falta": not presente,
            }
        )

        for chave in (tipo_dia, "geral"):
            resumo[chave]["total"] += 1
            if presente:
                resumo[chave]["presencas"] += 1
            else:
                resumo[chave]["faltas"] += 1

    for item in resumo.values():
        item["percentual"] = (
            round((item["presencas"] / item["total"]) * 100, 1)
            if item["total"]
            else 0.0
        )

    # Histórico de faltas (culto + Escola Bíblica) e a sequência atual.
    faltas = []
    for registro in todos_registros:
        tipo_dia = servico_presenca.normalizar_tipo(registro.tipo)
        if tipo_dia == "escola_biblica":
            presente = pessoa.nome_chave in participantes_eb.get(
                registro.dia, set()
            )
        else:
            presente = pessoa.nome_chave not in dias_culto.get(
                registro.dia, set()
            )
        if not presente:
            faltas.append(
                {
                    "dia": registro.dia,
                    "data": servico_presenca.data_br(registro.dia),
                    "tipo": tipo_dia,
                    "tipo_rotulo": servico_presenca.rotulo_tipo(tipo_dia),
                }
            )
            if len(faltas) >= 60:
                break

    dias_todos = servico_presenca.carregar_dias(session)
    ultimo_dia = todos_registros[0].dia if todos_registros else ""
    sequencia_atual = (
        servico_presenca.faltas_consecutivas(
            pessoa.nome_chave, ultimo_dia, dias_todos
        )
        if ultimo_dia
        else 0
    )
    inicio = (
        servico_presenca.inicio_sequencia(
            pessoa.nome_chave, ultimo_dia, dias_todos
        )
        if ultimo_dia
        else None
    )
    visita = session.exec(
        select(Visita).where(Visita.nome_chave == pessoa.nome_chave)
    ).first()
    visita_dia = visita.dia if visita else None
    precisa_visita = sequencia_atual >= servico_presenca.LIMITE_VISITA and not (
        visita_dia and inicio and visita_dia >= inicio
    )

    nomes_igrejas = servico_igrejas.mapa(session)
    return {
        "pessoa": {
            "id": int(pessoa.id or 0),
            "nome": pessoa.nome,
            "grupo": pessoa.grupo,
            "igreja_id": getattr(pessoa, "igreja_id", None),
            "igreja_nome": nomes_igrejas.get(
                getattr(pessoa, "igreja_id", None), ""
            ),
        },
        "limite": limite,
        "eventos": eventos,
        "resumo": resumo,
        "faltas": faltas,
        "sequencia": {
            "atual": sequencia_atual,
            "inicio": inicio,
            "inicio_data": servico_presenca.data_br(inicio) if inicio else None,
            "limite": servico_presenca.LIMITE_VISITA,
            "precisa_visita": precisa_visita,
            "visita_avisada_em": (
                servico_presenca.data_br(visita_dia) if visita_dia else None
            ),
        },
    }


# ---------------------------------------------------------------------------
# Números
# ---------------------------------------------------------------------------
@router.get("/numeros")
def numeros(
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    pessoas = _pessoas_do_escopo(session, user)
    contatos = servico_presenca.contatos(session)

    chave_cache = cache.chave("contatos", user.instancia)
    dados_whats, _ = cache.ler(chave_cache)

    itens = []
    for pessoa in pessoas:
        numero = _numero(pessoa, contatos)
        itens.append(
            {
                "id": int(pessoa.id or 0),
                "nome": pessoa.nome,
                "nome_chave": pessoa.nome_chave,
                "grupo": pessoa.grupo,
                "telefone": pessoa.telefone,
                "numero": numero,
                "numero_formatado": evolution.formatar_numero(numero) if numero else "",
                "vinculado": bool(numero),
            }
        )

    itens.sort(key=lambda item: item["nome_chave"])
    com_numero = sum(1 for item in itens if item["vinculado"])

    return {
        "total": len(itens),
        "com_numero": com_numero,
        "sem_numero": len(itens) - com_numero,
        "contatos_whats": len(dados_whats or {}),
        "sincronizando": cache.sincronizando(chave_cache),
        "erro": cache.erro(chave_cache),
        "pessoas": itens,
    }


@router.post("/numeros")
def salvar_numero(
    dados: NumeroEntrada,
    session: Session = Depends(get_session),
    _: User = Depends(usuario_atual),
) -> dict:
    chave = servico_pessoas.normalizar_nome(dados.nome_chave or dados.nome)
    if not chave:
        raise HTTPException(status_code=400, detail="Informe a pessoa.")

    jid = str(dados.jid or "").strip()
    if jid and not jid.endswith("@g.us"):
        jid = re.sub(r"\D", "", jid)
        if not jid:
            raise HTTPException(status_code=400, detail="Número inválido.")
        if not (10 <= len(jid) <= 15):
            raise HTTPException(
                status_code=400,
                detail="Número incompleto. Use DDI + DDD + número.",
            )

    contato = servico_presenca.salvar_contato(session, dados.nome, chave, jid)
    return {
        "ok": True,
        "nome_chave": chave,
        "jid": contato.jid if contato else "",
        "numero": evolution.formatar_numero(contato.jid) if contato else "",
    }


@router.post("/numeros/vincular")
def vincular(
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    chave_cache = cache.chave("contatos", user.instancia)
    dados_whats, _ = cache.ler(chave_cache)

    if dados_whats is None:
        cache.sincronizar(
            chave_cache, lambda: evolution.buscar_contatos(user.instancia)
        )
        return {
            "novos": 0,
            "sincronizando": cache.sincronizando(chave_cache),
            "erro": cache.erro(chave_cache),
            "contatos_whats": 0,
        }

    pessoas = servico_pessoas.listar(session, fonte="icm")
    novos = servico_presenca.vincular_automaticamente(
        session,
        dados_whats,
        [(pessoa.nome, pessoa.nome_chave) for pessoa in pessoas],
    )

    return {
        "novos": novos,
        "sincronizando": cache.sincronizando(chave_cache),
        "erro": cache.erro(chave_cache),
        "contatos_whats": len(dados_whats),
    }


# ---------------------------------------------------------------------------
# Mensagens
# ---------------------------------------------------------------------------
@router.get("/mensagens")
def mensagens(
    session: Session = Depends(get_session),
    user: User = Depends(usuario_atual),
) -> dict:
    textos = servico_presenca.carregar_mensagens(session)
    pessoas = _pessoas_do_escopo(session, user)
    exemplo = pessoas[0].nome if pessoas else "Maria"
    dia = _hoje()

    return {
        "mensagens": textos,
        "limite_visita": servico_presenca.LIMITE_VISITA,
        "exemplo": {
            "responsavel": "Líder do grupo",
            "nomes": [exemplo],
            "data": servico_presenca.data_br(dia),
            "falta": servico_presenca.montar_texto(
                textos["falta"],
                responsavel="Líder do grupo",
                nomes=[exemplo],
                dia=dia,
            ),
            "visita": servico_presenca.montar_texto(
                textos["visita"],
                responsavel="Líder do grupo",
                nomes=[exemplo],
                dia=dia,
                limite=servico_presenca.LIMITE_VISITA,
            ),
        },
    }


@router.put("/mensagens")
def salvar_mensagens(
    dados: MensagensEntrada,
    session: Session = Depends(get_session),
    _: User = Depends(usuario_atual),
) -> dict:
    if len(dados.falta) > LIMITE_TEXTO or len(dados.visita) > LIMITE_TEXTO:
        raise HTTPException(
            status_code=400,
            detail=f"Mensagem muito longa (máximo {LIMITE_TEXTO} caracteres).",
        )

    textos = servico_presenca.salvar_mensagens(session, dados.falta, dados.visita)
    return {"ok": True, "mensagens": textos}
