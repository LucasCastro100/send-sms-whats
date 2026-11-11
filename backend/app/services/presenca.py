"""Controle de presença: faltas por dia, números e mensagens.

O Streamlit guardava tudo em `data/presencas.json`, `data/contatos_membros.json`
e `data/mensagens_presenca.json`. Agora fica no banco:

- `presencas`              -> dias conferidos (culto e Escola Bíblica)
- `faltas`                 -> quem faltou em cada dia/tipo
- `presenca_participantes` -> quem participou da Escola Bíblica
- `visitas`                -> última vez que a mensagem de visita foi avisada
- `contatos_membros`       -> nome da pessoa -> JID/número do WhatsApp
- `mensagens_presenca`     -> textos de falta e de visita

O aviso de falta/visita não vai para a vida: vai para o responsável do grupo
de assistência e para o pastor da igreja da vida (ver `api/presenca.py`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from sqlmodel import Session, select

from ..models import (
    ContatoMembro,
    Falta,
    MensagemPresenca,
    PessoaICM,
    PresencaDia,
    PresencaParticipante,
    Visita,
)
from .pessoas import normalizar_nome

# Quantas faltas/ausências seguidas disparam a mensagem de visita.
LIMITE_VISITA = 7

TIPOS = ("culto", "escola_biblica")
TIPO_PADRAO = "culto"
ROTULOS = {"culto": "Culto", "escola_biblica": "Escola Bíblica"}

MENSAGENS_PADRAO = {
    "falta": (
        "Olá, {responsavel}! No {tipo} de {data}, faltaram {total} vida(s): "
        "{nomes}. Contamos com a sua visita e oração. 🙏"
    ),
    "visita": (
        "Olá, {responsavel}! Estas vidas estão há {limite} ou mais ausências "
        "seguidas e precisam de visita: {nomes}. 🙏"
    ),
}

CHAVES_MENSAGEM = ("falta", "visita")

# As mensagens antigas eram escritas para a própria vida. As novas ficam em
# chaves diferentes para o texto antigo não ser reaproveitado por engano.
CHAVES_BANCO = {
    "falta": "falta_responsavel",
    "visita": "visita_responsavel",
}


# ---------------------------------------------------------------------------
# Tipos de lançamento
# ---------------------------------------------------------------------------
def normalizar_tipo(valor: object) -> str:
    tipo = str(valor or "").strip().lower()
    return tipo if tipo in TIPOS else TIPO_PADRAO


def rotulo_tipo(valor: object) -> str:
    return ROTULOS[normalizar_tipo(valor)]


# ---------------------------------------------------------------------------
# Datas
# ---------------------------------------------------------------------------
def dia_valido(dia: str) -> bool:
    try:
        datetime.strptime(str(dia), "%Y-%m-%d")
    except (TypeError, ValueError):
        return False
    return True


def data_br(dia: str) -> str:
    """`2026-11-07` -> `07/11/2026` (devolve o original se não der)."""
    try:
        return datetime.strptime(str(dia), "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return str(dia)


# ---------------------------------------------------------------------------
# Faltas por dia
# ---------------------------------------------------------------------------
def carregar_dias(
    session: Session, tipo: Optional[str] = None
) -> Dict[str, Set[str]]:
    """Dia conferido -> conjunto de `nome_chave` faltantes.

    Sem `tipo`, junta culto e Escola Bíblica (é o mapa usado na sequência de
    ausências que dispara a visita).
    """
    consulta = select(PresencaDia)
    consulta_faltas = select(Falta)
    if tipo is not None:
        tipo = normalizar_tipo(tipo)
        consulta = consulta.where(PresencaDia.tipo == tipo)
        consulta_faltas = consulta_faltas.where(Falta.tipo == tipo)

    dias: Dict[str, Set[str]] = {
        row.dia: set() for row in session.exec(consulta).all()
    }
    for falta in session.exec(consulta_faltas).all():
        dias.setdefault(falta.dia, set()).add(falta.nome_chave)
    return dias


def faltas_do_dia(
    session: Session, dia: str, tipo: str = TIPO_PADRAO
) -> Set[str]:
    tipo = normalizar_tipo(tipo)
    return {
        falta.nome_chave
        for falta in session.exec(
            select(Falta).where(Falta.dia == dia, Falta.tipo == tipo)
        ).all()
    }


def participantes_do_dia(
    session: Session, dia: str, tipo: str = "escola_biblica"
) -> Set[str]:
    tipo = normalizar_tipo(tipo)
    return {
        item.nome_chave
        for item in session.exec(
            select(PresencaParticipante).where(
                PresencaParticipante.dia == dia,
                PresencaParticipante.tipo == tipo,
            )
        ).all()
    }


def carregar_participantes(
    session: Session, tipo: str = "escola_biblica"
) -> Dict[str, Set[str]]:
    tipo = normalizar_tipo(tipo)
    participantes: Dict[str, Set[str]] = {}
    for item in session.exec(
        select(PresencaParticipante).where(PresencaParticipante.tipo == tipo)
    ).all():
        participantes.setdefault(item.dia, set()).add(item.nome_chave)
    return participantes


def dia_conferido(session: Session, dia: str, tipo: str = TIPO_PADRAO) -> bool:
    tipo = normalizar_tipo(tipo)
    return (
        session.exec(
            select(PresencaDia).where(
                PresencaDia.dia == dia, PresencaDia.tipo == tipo
            )
        ).first()
        is not None
    )


def _nomes_por_chave(session: Session, chaves: Set[str]) -> Dict[str, str]:
    if not chaves:
        return {}
    pessoas = session.exec(
        select(PessoaICM).where(PessoaICM.nome_chave.in_(chaves))  # type: ignore[attr-defined]
    ).all()
    return {pessoa.nome_chave: pessoa.nome for pessoa in pessoas}


def elenco_icm(session: Session) -> List[Tuple[str, str]]:
    """Todas as vidas ativas do ICM, como `(nome, nome_chave)`."""
    return [
        (pessoa.nome, pessoa.nome_chave)
        for pessoa in session.exec(
            select(PessoaICM).where(PessoaICM.ativo == True)  # noqa: E712
        ).all()
    ]


def salvar_presenca(
    session: Session,
    dia: str,
    tipo: str,
    nomes_chave: List[str],
    elenco: Optional[List[Tuple[str, str]]] = None,
) -> int:
    """Grava o lançamento de um dia.

    - `culto`: a lista recebida é a de **faltantes**.
    - `escola_biblica`: a lista recebida é a de **participantes**; quem está no
      elenco e não participou entra como falta (é o que mantém a sequência de
      ausências correta para o aviso de visita).

    O dia é guardado mesmo quando a lista está vazia: é assim que o sistema
    sabe que a presença foi conferida e que a sequência de faltas de alguém
    foi quebrada.
    """
    tipo = normalizar_tipo(tipo)
    chaves = {normalizar_nome(nome) for nome in nomes_chave if str(nome).strip()}

    registro = session.exec(
        select(PresencaDia).where(
            PresencaDia.dia == dia, PresencaDia.tipo == tipo
        )
    ).first()
    if registro:
        registro.atualizado_em = datetime.utcnow()
        session.add(registro)
    else:
        session.add(PresencaDia(dia=dia, tipo=tipo))

    for falta in session.exec(
        select(Falta).where(Falta.dia == dia, Falta.tipo == tipo)
    ).all():
        session.delete(falta)
    for item in session.exec(
        select(PresencaParticipante).where(
            PresencaParticipante.dia == dia, PresencaParticipante.tipo == tipo
        )
    ).all():
        session.delete(item)
    session.flush()

    if tipo == "escola_biblica":
        nomes = _nomes_por_chave(session, chaves)
        for chave in sorted(chaves):
            session.add(
                PresencaParticipante(
                    dia=dia,
                    tipo=tipo,
                    nome=nomes.get(chave, chave),
                    nome_chave=chave,
                )
            )

        elenco = elenco if elenco is not None else elenco_icm(session)
        elenco_chaves = {normalizar_nome(chave) for _, chave in elenco}
        faltantes = elenco_chaves - chaves
        nomes_faltantes = {
            normalizar_nome(chave): nome for nome, chave in elenco
        }
        for chave in sorted(faltantes):
            session.add(
                Falta(
                    dia=dia,
                    tipo=tipo,
                    nome=nomes_faltantes.get(chave, chave),
                    nome_chave=chave,
                )
            )
    else:
        nomes = _nomes_por_chave(session, chaves)
        for chave in sorted(chaves):
            session.add(
                Falta(
                    dia=dia,
                    tipo=tipo,
                    nome=nomes.get(chave, chave),
                    nome_chave=chave,
                )
            )

    session.commit()
    return len(chaves)


def salvar_faltas(
    session: Session, dia: str, nomes_chave: List[str], tipo: str = TIPO_PADRAO
) -> int:
    """Compatibilidade: salva faltas do culto."""
    return salvar_presenca(session, dia, tipo, nomes_chave)


def faltas_consecutivas(chave: str, dia: str, dias: Dict[str, Set[str]]) -> int:
    """Quantas ausências seguidas a pessoa tem, olhando os dias já registrados.

    O mapa `dias` pode juntar culto e Escola Bíblica: os dois contam na mesma
    sequência.
    """
    chave = normalizar_nome(chave)

    total = 0
    for registro in sorted((d for d in dias if d <= dia), reverse=True):
        if chave in dias[registro]:
            total += 1
        else:
            break
    return total


def inicio_sequencia(
    chave: str, dia: str, dias: Dict[str, Set[str]]
) -> Optional[str]:
    """Primeiro dia da sequência de faltas atual (None se não houver)."""
    chave = normalizar_nome(chave)

    inicio: Optional[str] = None
    for registro in sorted((d for d in dias if d <= dia), reverse=True):
        if chave in dias[registro]:
            inicio = registro
        else:
            break
    return inicio


def precisa_visita(
    session: Session,
    chave: str,
    dia: str,
    dias: Optional[Dict[str, Set[str]]] = None,
    limite: int = LIMITE_VISITA,
    visitas: Optional[Dict[str, Visita]] = None,
) -> Tuple[bool, int]:
    """Diz se a pessoa já passou do limite e ainda não foi avisada nesta sequência."""
    chave = normalizar_nome(chave)
    dias = dias if dias is not None else carregar_dias(session)

    sequencia = faltas_consecutivas(chave, dia, dias)
    if sequencia < limite:
        return False, sequencia

    if visitas is not None:
        registro = visitas.get(chave)
    else:
        registro = session.exec(
            select(Visita).where(Visita.nome_chave == chave)
        ).first()
    inicio = inicio_sequencia(chave, dia, dias)

    # Se a visita já foi avisada depois do início desta sequência, não repete.
    if registro and inicio and str(registro.dia or "") >= inicio:
        return False, sequencia

    return True, sequencia


def registrar_visita(
    session: Session, nome: str, chave: str, dia: str, faltas: int
) -> None:
    """Marca que a mensagem de visita foi enviada nesta sequência."""
    chave = normalizar_nome(chave)

    registro = session.exec(
        select(Visita).where(Visita.nome_chave == chave)
    ).first()
    if not registro:
        registro = Visita(nome=nome, nome_chave=chave)

    registro.nome = nome or registro.nome
    registro.dia = dia
    registro.faltas = int(faltas)
    registro.atualizado_em = datetime.utcnow()
    session.add(registro)
    session.commit()


# ---------------------------------------------------------------------------
# Números das pessoas (nome -> JID/número)
# ---------------------------------------------------------------------------
def contatos(session: Session) -> Dict[str, ContatoMembro]:
    return {
        contato.nome_chave: contato
        for contato in session.exec(select(ContatoMembro)).all()
    }


def salvar_contato(
    session: Session, nome: str, chave: str, jid: str
) -> Optional[ContatoMembro]:
    """Vincula (ou remove, com `jid` vazio) o número de uma pessoa."""
    chave = normalizar_nome(chave or nome)
    registro = session.exec(
        select(ContatoMembro).where(ContatoMembro.nome_chave == chave)
    ).first()

    alvo = str(jid or "").strip()
    if not alvo:
        if registro:
            session.delete(registro)
            session.commit()
        return None

    if not registro:
        registro = ContatoMembro(nome=nome or chave, nome_chave=chave, jid=alvo)

    registro.nome = nome or registro.nome
    registro.jid = alvo
    registro.atualizado_em = datetime.utcnow()
    session.add(registro)
    session.commit()
    session.refresh(registro)
    return registro


def vincular_automaticamente(
    session: Session,
    contatos_whats: Dict[str, str],
    nomes: List[Tuple[str, str]],
) -> int:
    """Casa nome da pessoa com o nome do contato do WhatsApp (nome completo).

    `nomes` é uma lista de `(nome, nome_chave)`. Devolve quantos vínculos
    novos foram criados.
    """
    por_nome = {
        normalizar_nome(nome): jid for jid, nome in (contatos_whats or {}).items()
    }
    vinculados = contatos(session)

    novos = 0
    for nome, chave in nomes:
        chave = normalizar_nome(chave or nome)
        if chave in vinculados:
            continue
        jid = por_nome.get(chave)
        if not jid:
            continue
        session.add(ContatoMembro(nome=nome or chave, nome_chave=chave, jid=jid))
        novos += 1

    if novos:
        session.commit()
    return novos


# ---------------------------------------------------------------------------
# Mensagens
# ---------------------------------------------------------------------------
def carregar_mensagens(session: Session) -> Dict[str, str]:
    mensagens = dict(MENSAGENS_PADRAO)
    por_banco = {valor: chave for chave, valor in CHAVES_BANCO.items()}
    for item in session.exec(select(MensagemPresenca)).all():
        chave = por_banco.get(item.chave)
        if chave and str(item.texto or "").strip():
            mensagens[chave] = item.texto
    return mensagens


def salvar_mensagens(session: Session, falta: str, visita: str) -> Dict[str, str]:
    textos = {
        "falta": str(falta or "").strip() or MENSAGENS_PADRAO["falta"],
        "visita": str(visita or "").strip() or MENSAGENS_PADRAO["visita"],
    }

    for chave, texto in textos.items():
        chave_banco = CHAVES_BANCO[chave]
        registro = session.exec(
            select(MensagemPresenca).where(MensagemPresenca.chave == chave_banco)
        ).first()
        if not registro:
            registro = MensagemPresenca(chave=chave_banco, texto=texto)
        registro.texto = texto
        registro.atualizado_em = datetime.utcnow()
        session.add(registro)

    session.commit()
    return textos


def montar_texto(
    modelo: str,
    *,
    responsavel: str = "",
    nomes: Optional[List[str]] = None,
    dia: str = "",
    tipo: str = TIPO_PADRAO,
    limite: int = LIMITE_VISITA,
) -> str:
    """Troca os marcadores do modelo pelos dados do aviso."""
    lista = [str(nome).strip() for nome in (nomes or []) if str(nome).strip()]
    texto = str(modelo or "")
    trocas = {
        "{responsavel}": responsavel or "responsável",
        "{nomes}": ", ".join(lista),
        "{data}": data_br(dia),
        "{tipo}": rotulo_tipo(tipo),
        "{total}": str(len(lista)),
        "{faltas}": str(len(lista)),
        "{limite}": str(limite),
        "{nome}": responsavel or "responsável",
    }
    for marcador, valor in trocas.items():
        texto = texto.replace(marcador, valor)
    return texto
