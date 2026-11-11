"""Modelos do banco."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class GrupoAssistencia(SQLModel, table=True):
    """Grupo de assistência do ICM (ex.: `1- LUCAS / PAULO`)."""

    __tablename__ = "grupos_assistencia"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(index=True, unique=True, max_length=160)
    ativo: bool = Field(default=True)
    # Quem recebe os avisos de falta/visita das vidas do grupo.
    responsavel_nome: str = Field(default="", max_length=160)
    responsavel_whatsapp: str = Field(default="", max_length=20)
    criado_em: datetime = Field(default_factory=datetime.utcnow)


class Igreja(SQLModel, table=True):
    """Igreja de origem das vidas da lista ICM (ex.: `IGREJA BOA VISTA`)."""

    __tablename__ = "igrejas"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(index=True, unique=True, max_length=160)
    ativo: bool = Field(default=True)
    # Pastor que recebe os avisos de falta/visita das vidas da igreja.
    pastor_nome: str = Field(default="", max_length=160)
    pastor_whatsapp: str = Field(default="", max_length=20)
    criado_em: datetime = Field(default_factory=datetime.utcnow)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(max_length=80)
    usuario: str = Field(index=True, unique=True, max_length=120)
    senha_hash: str
    instancia: str = Field(index=True, max_length=80)
    admin: bool = Field(default=False)
    funcao: str = Field(default="lider", max_length=20)
    ativo: bool = Field(default=True)
    grupo_id: Optional[int] = Field(
        default=None, foreign_key="grupos_assistencia.id", index=True
    )
    criado_em: datetime = Field(default_factory=datetime.utcnow)


class PessoaBase(SQLModel):
    """Campos comuns dos aniversariantes (cada fonte tem a sua tabela).

    A chave natural é o `nome_chave`: nome em maiúsculas com espaços simples,
    igual ao que o Streamlit usava nos arquivos JSON.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(max_length=160)
    nome_chave: str = Field(index=True, max_length=160)

    dia: Optional[int] = None
    mes: Optional[int] = None
    ano: Optional[int] = None
    grupo: str = Field(default="", max_length=160)
    telefone: str = Field(default="", max_length=20)
    foto: str = Field(default="", max_length=300)

    # Dados do sistema da igreja (listagem geral + listagens por grupo)
    situacao: str = Field(default="", max_length=40)
    categoria: str = Field(default="", max_length=40)
    tel_residencial: str = Field(default="", max_length=20)
    tel_comercial: str = Field(default="", max_length=20)
    celular: str = Field(default="", max_length=20)

    # Visitação: a data é a fonte da verdade; os dias são calculados.
    ultima_visita: Optional[date] = None
    dias_sem_visita: Optional[int] = None
    visitas_referencia: Optional[date] = None

    # Campos manuais: a importação só preenche quando estão vazios.
    genero: Optional[str] = Field(default=None, max_length=1)
    excluido: bool = Field(default=False)

    ativo: bool = Field(default=True)
    criado_em: datetime = Field(default_factory=datetime.utcnow)
    atualizado_em: datetime = Field(default_factory=datetime.utcnow)
    visto_em: Optional[datetime] = None

    @property
    def fonte(self) -> str:
        """Nome da tabela, que é o nome da fonte (`icm` ou `zoom`)."""
        return str(self.__tablename__)


class PessoaICM(PessoaBase, table=True):
    """Aniversariantes do conjunto ICM (tabela `icm`)."""

    __tablename__ = "icm"
    __table_args__ = (UniqueConstraint("nome_chave", name="uq_icm_nome"),)

    # Igreja de origem da vida — só a lista ICM tem esse vínculo.
    igreja_id: Optional[int] = Field(
        default=None, foreign_key="igrejas.id", index=True
    )


class PessoaZoom(PessoaBase, table=True):
    """Aniversariantes do conjunto Zoom (tabela `zoom`)."""

    __tablename__ = "zoom"
    __table_args__ = (UniqueConstraint("nome_chave", name="uq_zoom_nome"),)


MODELOS_PESSOA = {"icm": PessoaICM, "zoom": PessoaZoom}


class Importacao(SQLModel, table=True):
    """Histórico de cada arquivo importado."""

    __tablename__ = "importacoes"

    id: Optional[int] = Field(default=None, primary_key=True)
    arquivo: str = Field(max_length=200)
    formato: str = Field(max_length=10)
    fonte: str = Field(index=True, max_length=20)
    modo: str = Field(default="mesclar", max_length=20)

    usuario_id: Optional[int] = Field(default=None, foreign_key="users.id")
    usuario: str = Field(default="", max_length=120)

    inseridos: int = Field(default=0)
    atualizados: int = Field(default=0)
    iguais: int = Field(default=0)
    ausentes: int = Field(default=0)
    conflitos: int = Field(default=0)
    detalhes: str = Field(default="", max_length=20000)

    criado_em: datetime = Field(default_factory=datetime.utcnow)


class Agendamento(SQLModel, table=True):
    """Envio de mensagem agendado para um destino (grupo ou número)."""

    __tablename__ = "agendamentos"

    id: Optional[int] = Field(default=None, primary_key=True)
    texto: str = Field(max_length=4000)
    destino: str = Field(max_length=120)
    nome: str = Field(default="", max_length=160)

    # Sempre em UTC (naive); a tela mostra no horário de Brasília.
    quando: datetime = Field(index=True)
    status: str = Field(default="pendente", index=True, max_length=20)
    resultado: str = Field(default="", max_length=2000)

    instancia: str = Field(max_length=80)
    usuario_id: Optional[int] = Field(default=None, foreign_key="users.id")
    usuario: str = Field(default="", max_length=120)

    criado_em: datetime = Field(default_factory=datetime.utcnow)
    executado_em: Optional[datetime] = None


class Disparo(SQLModel, table=True):
    """Registro do disparo diário automático (um por dia e por fonte)."""

    __tablename__ = "disparos"
    __table_args__ = (
        UniqueConstraint("data", "fonte", name="uq_disparos_data_fonte"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    # Dia de referência no horário de Brasília (YYYY-MM-DD).
    data: str = Field(index=True, max_length=10)
    fonte: str = Field(default="icm", max_length=20)

    destino: str = Field(default="", max_length=120)
    nome: str = Field(default="", max_length=160)
    citados: int = Field(default=0)

    # enviado | vazio | erro
    status: str = Field(default="pendente", index=True, max_length=20)
    resultado: str = Field(default="", max_length=2000)
    executado_em: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Presença
# ---------------------------------------------------------------------------
class PresencaDia(SQLModel, table=True):
    """Dia em que a presença foi conferida (mesmo sem nenhuma falta).

    `tipo` separa o culto da Escola Bíblica: o mesmo dia pode ter os dois.
    """

    __tablename__ = "presencas"
    __table_args__ = (
        UniqueConstraint("dia", "tipo", name="uq_presencas_dia_tipo"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    # YYYY-MM-DD, no horário de Brasília.
    dia: str = Field(index=True, max_length=10)
    # culto | escola_biblica
    tipo: str = Field(default="culto", index=True, max_length=20)

    criado_em: datetime = Field(default_factory=datetime.utcnow)
    atualizado_em: datetime = Field(default_factory=datetime.utcnow)


class Falta(SQLModel, table=True):
    """Uma pessoa ausente em um dia conferido (culto ou Escola Bíblica)."""

    __tablename__ = "faltas"
    __table_args__ = (
        UniqueConstraint(
            "dia", "tipo", "nome_chave", name="uq_faltas_dia_tipo_nome"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    dia: str = Field(index=True, max_length=10)
    tipo: str = Field(default="culto", index=True, max_length=20)
    nome: str = Field(default="", max_length=160)
    nome_chave: str = Field(index=True, max_length=160)


class PresencaParticipante(SQLModel, table=True):
    """Quem participou da Escola Bíblica em um dia.

    No culto a lista guardada é a de faltas; na Escola Bíblica o lançamento é
    o contrário (marca-se quem participou), então os presentes ficam aqui.
    """

    __tablename__ = "presenca_participantes"
    __table_args__ = (
        UniqueConstraint(
            "dia", "tipo", "nome_chave", name="uq_participantes_dia_tipo_nome"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    dia: str = Field(index=True, max_length=10)
    tipo: str = Field(default="escola_biblica", index=True, max_length=20)
    nome: str = Field(default="", max_length=160)
    nome_chave: str = Field(index=True, max_length=160)


class Visita(SQLModel, table=True):
    """Última mensagem de visita avisada (uma por pessoa)."""

    __tablename__ = "visitas"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(default="", max_length=160)
    nome_chave: str = Field(index=True, unique=True, max_length=160)
    # Dia e tamanho da sequência em que a visita foi avisada.
    dia: str = Field(default="", max_length=10)
    faltas: int = Field(default=0)

    atualizado_em: datetime = Field(default_factory=datetime.utcnow)


class ContatoMembro(SQLModel, table=True):
    """Número de WhatsApp vinculado a uma pessoa da lista de presença."""

    __tablename__ = "contatos_membros"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(default="", max_length=160)
    nome_chave: str = Field(index=True, unique=True, max_length=160)
    jid: str = Field(max_length=120)

    atualizado_em: datetime = Field(default_factory=datetime.utcnow)


class MensagemPresenca(SQLModel, table=True):
    """Textos de falta e de visita (`chave` = falta | visita)."""

    __tablename__ = "mensagens_presenca"

    id: Optional[int] = Field(default=None, primary_key=True)
    chave: str = Field(index=True, unique=True, max_length=20)
    texto: str = Field(max_length=4000)

    atualizado_em: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Eventos da igreja (Maanaim, encontros, retiros...)
# ---------------------------------------------------------------------------
class Evento(SQLModel, table=True):
    """Evento com data própria; a vida participa ou não de cada um."""

    __tablename__ = "eventos"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(max_length=120)
    data: date = Field(index=True)
    local: str = Field(default="", max_length=160)
    descricao: str = Field(default="", max_length=1000)

    criado_por: str = Field(default="", max_length=120)
    criado_em: datetime = Field(default_factory=datetime.utcnow)
    atualizado_em: datetime = Field(default_factory=datetime.utcnow)


class EventoParticipante(SQLModel, table=True):
    """Vida do ICM que participou de um evento."""

    __tablename__ = "evento_participantes"
    __table_args__ = (
        UniqueConstraint(
            "evento_id", "nome_chave", name="uq_evento_participante"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    evento_id: int = Field(foreign_key="eventos.id", index=True)
    nome: str = Field(default="", max_length=160)
    nome_chave: str = Field(index=True, max_length=160)
    criado_em: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Observações da ficha da vida
# ---------------------------------------------------------------------------
class Observacao(SQLModel, table=True):
    """Anotação livre feita pelo líder/pastor sobre uma vida do ICM."""

    __tablename__ = "observacoes"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(default="", max_length=160)
    nome_chave: str = Field(index=True, max_length=160)
    texto: str = Field(max_length=2000)
    criado_por: str = Field(default="", max_length=120)
    criado_em: datetime = Field(default_factory=datetime.utcnow)
    atualizado_em: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Motivos de oração
# ---------------------------------------------------------------------------
class MotivoOracao(SQLModel, table=True):
    """Pedido de oração lançado na ficha de uma vida do ICM."""

    __tablename__ = "motivos_oracao"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(default="", max_length=160)
    nome_chave: str = Field(index=True, max_length=160)
    texto: str = Field(max_length=1000)

    # aberto | atendido
    status: str = Field(default="aberto", index=True, max_length=20)
    criado_por: str = Field(default="", max_length=120)

    criado_em: datetime = Field(default_factory=datetime.utcnow)
    atualizado_em: datetime = Field(default_factory=datetime.utcnow)
    atendido_em: Optional[datetime] = None
