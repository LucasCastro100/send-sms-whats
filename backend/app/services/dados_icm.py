"""Junção dos dados do sistema da igreja (PDFs) na tabela `icm`.

O sistema da igreja exporta três listagens diferentes:

- ``listagem-geral.pdf`` — cadastro: nome completo, situação, grupo de
  assistência, categoria e sexo. Não traz aniversário.
- ``listagem-membros_gN_contato.pdf`` — complemento por grupo de
  assistência: aniversário, telefones e "S/ Visitas".
- ``listagem-membros_gN_foto(s).pdf`` — hoje vem como HTML do portal, sem
  dados; não é lido aqui.

A geral abrevia os nomes do meio (``ANA PAULA M. AMARAL``) e o contato
também, então a junção casa por nome: primeiro + último nome, desempatando
pelas iniciais do meio e pelo grupo. Gênero e exclusão são manuais e a
junção nunca os sobrescreve.

"S/ Visitas" é um contador que envelhece: a importação converte para
``ultima_visita = referência − N dias`` e guarda o número original em
``dias_sem_visita``/``visitas_referencia`` só para conferência.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Sequence

from pypdf import PdfReader
from sqlmodel import Session, select

from ..models import PessoaICM
from . import pessoas as servico_pessoas

ARQUIVO_GERAL = "listagem-geral.pdf"
ARQUIVOS_CONTATO = (
    "listagem-membros_g1_contato.pdf",
    "listagem-membros_g2_contato.pdf",
    "listagem-membros_g3_contato.pdf",
)

CATEGORIAS = (
    "Criança de Colo 0-3",
    "Criança (Pequeno) 3-7",
    "Criança (Intermediário) 7-11",
    "Adolescente",
    "Jovem",
    "Adulto",
)

# Pontuação do casamento de nomes.
PONTOS_EXATO = 1000
PONTOS_MEIO = 600
PONTOS_FRACO = 100


# ---------------------------------------------------------------------------
# Normalização e casamento de nomes
# ---------------------------------------------------------------------------
def _sem_acento(texto: object) -> str:
    return (
        unicodedata.normalize("NFKD", str(texto or ""))
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def normalizar(texto: object) -> str:
    """Maiúsculas, sem acento e só letras/espaços — a chave de comparação."""
    limpo = re.sub(r"[^A-Z ]", " ", _sem_acento(texto).upper())
    return re.sub(r"\s+", " ", limpo).strip()


def _tokens(nome: object) -> list[str]:
    return normalizar(nome).split()


def _e_subsequencia(menor: Sequence[str], maior: Sequence[str]) -> bool:
    if not menor:
        return True
    if len(menor) > len(maior):
        return False
    resto = list(maior)
    for item in menor:
        if item not in resto:
            return False
        resto = resto[resto.index(item) + 1 :]
    return True


def pontuar(nome: object, candidato: object) -> int:
    """Quanto `nome` parece com `candidato` (0 = não é a mesma pessoa)."""
    a, b = _tokens(nome), _tokens(candidato)
    if not a or not b:
        return 0
    if a == b:
        return PONTOS_EXATO
    if a[0] != b[0] or a[-1] != b[-1]:
        return 0

    meio_a = [token[0] for token in a[1:-1]]
    meio_b = [token[0] for token in b[1:-1]]
    if _e_subsequencia(meio_a, meio_b) or _e_subsequencia(meio_b, meio_a):
        return PONTOS_MEIO + min(len(meio_a), len(meio_b))
    return PONTOS_FRACO


# ---------------------------------------------------------------------------
# Leitura dos PDFs
# ---------------------------------------------------------------------------
def _paginas(caminho: Path) -> list[str]:
    leitor = PdfReader(str(caminho))
    return [pagina.extract_text(extraction_mode="layout") or "" for pagina in leitor.pages]


def _posicoes(cabecalho: str, rotulos: Sequence[str]) -> list[int]:
    """Posição de cada coluna no cabeçalho (layout preserva o alinhamento)."""
    posicoes: list[int] = []
    for rotulo in rotulos:
        indice = cabecalho.find(rotulo)
        if indice < 0:
            indice = _sem_acento(cabecalho).find(_sem_acento(rotulo))
        posicoes.append(indice)
    return posicoes


def _fatiar(linha: str, posicoes: Sequence[int]) -> list[str]:
    colunas: list[str] = []
    for numero, inicio in enumerate(posicoes):
        if inicio is None or inicio < 0:
            colunas.append("")
            continue
        fim = (
            posicoes[numero + 1]
            if numero + 1 < len(posicoes) and posicoes[numero + 1] > inicio
            else len(linha)
        )
        colunas.append(linha[inicio:fim].strip())
    return colunas


def _separar_categoria(grupo_bruto: str, categoria_bruta: str) -> tuple[str, str]:
    """A categoria transborda da coluna do grupo e é cortada ao meio.

    Ex.: ``2- VANDERLEY / JOSE ROBERTOAdul`` + ``to`` vira grupo
    ``2- VANDERLEY / JOSE ROBERTO`` e categoria ``Adulto``.
    """
    grupo_bruto = grupo_bruto.strip()
    categoria_bruta = categoria_bruta.strip()
    grupo_comparavel = _sem_acento(grupo_bruto).upper()
    resto = _sem_acento(categoria_bruta).upper().replace(" ", "")

    parcial: Optional[tuple[str, str]] = None
    for categoria in CATEGORIAS:
        alvo = _sem_acento(categoria).upper()
        for corte in range(len(alvo), 2, -1):
            prefixo = alvo[:corte]
            if not grupo_comparavel.endswith(prefixo):
                continue

            grupo = grupo_bruto[: len(grupo_bruto) - corte].strip()
            if not grupo or not grupo[0].isdigit():
                break

            # A coluna do grupo corta a palavra (``Cria`` + ``ça ...``): aceita
            # a categoria canônica quando o pedaço é o final dela.
            if corte == len(alvo) or (
                resto and alvo.replace(" ", "").endswith(resto)
            ):
                return grupo, categoria
            if parcial is None:
                parcial = (grupo, categoria_bruta)
            break

    return parcial or (grupo_bruto, categoria_bruta)


def _ler_data(texto: str) -> tuple[Optional[int], Optional[int], Optional[int], str]:
    """``dd/mm/aaaa`` → dia, mês, ano e um aviso quando o ano é suspeito."""
    achado = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", (texto or "").strip())
    if not achado:
        return None, None, None, ""
    dia, mes, ano = (int(parte) for parte in achado.groups())
    if not (1 <= dia <= 31 and 1 <= mes <= 12):
        return None, None, None, f"data inválida ({texto})"
    if not (1900 <= ano <= date.today().year):
        return dia, mes, None, f"ano inválido ({texto})"
    return dia, mes, ano, ""


@dataclass
class Registro:
    """Uma pessoa depois de juntar a listagem geral e o contato."""

    nome: str = ""
    nome_contato: str = ""
    grupo: str = ""
    situacao: str = ""
    categoria: str = ""
    sexo: str = ""
    dia: Optional[int] = None
    mes: Optional[int] = None
    ano: Optional[int] = None
    data_bruta: str = ""
    tel_residencial: str = ""
    tel_comercial: str = ""
    celular: str = ""
    visitas: Optional[int] = None
    problemas: list[str] = field(default_factory=list)

    @property
    def nomes(self) -> list[str]:
        return [nome for nome in (self.nome, self.nome_contato) if nome]

    @property
    def melhor_nome(self) -> str:
        """O nome mais completo entre a geral e o contato."""
        nome = ""
        for candidato in self.nomes:
            nome = _nome_preferido(nome, candidato)
        return nome


def ler_geral(caminho: Path) -> list[Registro]:
    """Listagem geral: cadastro de todo mundo (nome completo, grupo, sexo)."""
    registros: list[Registro] = []
    rotulos = ("Pessoa", "Situação", "Grupo de Assist", "Categoria", "Sexo")

    for texto in _paginas(caminho):
        posicoes: Optional[list[int]] = None
        for linha in texto.splitlines():
            if posicoes is None:
                if "Pessoa" in linha and "Sexo" in linha:
                    posicoes = _posicoes(linha, rotulos)
                continue

            if not re.match(r"^\s*\d+\s", linha):
                continue

            colunas = _fatiar(linha, posicoes)
            if not colunas[0]:
                continue

            grupo, categoria = _separar_categoria(colunas[2], colunas[3])
            registros.append(
                Registro(
                    nome=colunas[0],
                    grupo=grupo,
                    situacao=colunas[1],
                    categoria=categoria,
                    sexo=colunas[4].strip().upper()[:1],
                )
            )

    return registros


def ler_contato(caminho: Path) -> tuple[list[Registro], str]:
    """Listagem por grupo: aniversário, telefones e S/ Visitas."""
    registros: list[Registro] = []
    grupo_arquivo = ""
    referencia = ""
    rotulos = (
        "Pessoas",
        "Aniversário",
        "Tel. Residêncial",
        "Tel. Comercial",
        "Celular",
        "S/ Visitas",
    )

    for texto in _paginas(caminho):
        posicoes: Optional[list[int]] = None
        for linha in texto.splitlines():
            if linha.startswith("Grupo de Assistência:"):
                grupo_arquivo = linha.split(":", 1)[1].split("Referência")[0].strip()
            if "Referência:" in linha:
                achado = re.search(r"Referência:\s*(\d{2}/\d{2}/\d{4})", linha)
                if achado:
                    referencia = achado.group(1)

            if posicoes is None:
                if "Aniversário" in linha and "S/ Visitas" in linha:
                    posicoes = _posicoes(linha, rotulos)
                continue

            if not re.match(r"^\s*\d+\s", linha):
                continue

            colunas = _fatiar(linha, posicoes)
            if not colunas[0]:
                continue

            dia, mes, ano, aviso = _ler_data(colunas[1])
            registro = Registro(
                nome_contato=colunas[0],
                grupo=grupo_arquivo,
                data_bruta=colunas[1],
                dia=dia,
                mes=mes,
                ano=ano,
                tel_residencial=colunas[2],
                tel_comercial=colunas[3],
                celular=colunas[4],
            )
            if aviso:
                registro.problemas.append(aviso)
            if colunas[5].isdigit():
                registro.visitas = int(colunas[5])
            registros.append(registro)

    return registros, referencia


# ---------------------------------------------------------------------------
# Junção
# ---------------------------------------------------------------------------
@dataclass
class Relatorio:
    referencia: date
    registros: list[Registro] = field(default_factory=list)
    total_geral: int = 0
    total_contato: int = 0
    contato_sem_par: list[str] = field(default_factory=list)
    geral_sem_contato: list[str] = field(default_factory=list)
    ambiguos: list[str] = field(default_factory=list)
    problemas: list[str] = field(default_factory=list)
    telefones_suspeitos: list[str] = field(default_factory=list)
    sem_aniversario: list[str] = field(default_factory=list)

    def resumo(self) -> str:
        linhas = [
            f"Referência: {self.referencia.strftime('%d/%m/%Y')}",
            f"Geral: {self.total_geral} | Contato: {self.total_contato} | "
            f"Juntados: {len(self.registros)}",
            f"Sem aniversário: {len(self.sem_aniversario)}",
        ]
        if self.contato_sem_par:
            linhas.append(f"Contato sem par na geral: {self.contato_sem_par}")
        if self.geral_sem_contato:
            linhas.append(f"Geral sem contato: {self.geral_sem_contato}")
        if self.ambiguos:
            linhas.append(f"Nomes ambíguos: {self.ambiguos}")
        if self.telefones_suspeitos:
            linhas.append(f"Telefones suspeitos: {self.telefones_suspeitos}")
        if self.problemas:
            linhas.append(f"Problemas: {self.problemas}")
        return "\n".join(linhas)


def _melhor_par(
    nomes: Sequence[str],
    candidatos: Sequence[str],
    ignorar: Optional[set[int]] = None,
) -> tuple[Optional[int], list[int]]:
    """Índice do melhor candidato e os que empataram na maior pontuação."""
    ignorar = ignorar or set()
    pontos: list[tuple[int, int]] = []
    for indice, candidato in enumerate(candidatos):
        if indice in ignorar:
            continue
        melhor = max((pontuar(nome, candidato) for nome in nomes), default=0)
        if melhor > 0:
            pontos.append((indice, melhor))

    if not pontos:
        return None, []

    maior = max(ponto for _, ponto in pontos)
    empatados = [indice for indice, ponto in pontos if ponto == maior]
    return empatados[0], empatados


def juntar(pasta: Path, referencia: Optional[date] = None) -> Relatorio:
    """Lê os quatro PDFs com dados e devolve tudo já casado por pessoa."""
    pasta = Path(pasta)
    geral = ler_geral(pasta / ARQUIVO_GERAL)

    contatos: list[Registro] = []
    referencia_texto = ""
    for nome_arquivo in ARQUIVOS_CONTATO:
        caminho = pasta / nome_arquivo
        if not caminho.exists():
            continue
        lidos, referencia_arquivo = ler_contato(caminho)
        contatos.extend(lidos)
        referencia_texto = referencia_texto or referencia_arquivo

    relatorio = Relatorio(
        referencia=referencia or _data_de(referencia_texto) or date.today(),
        total_geral=len(geral),
        total_contato=len(contatos),
    )

    nomes_geral = [registro.nome for registro in geral]

    usados: set[int] = set()
    for contato in contatos:
        indice, empatados = _melhor_par(
            [contato.nome_contato], nomes_geral, ignorar=usados
        )

        # Empate: tenta o grupo de assistência do arquivo de contato.
        if indice is not None and len(empatados) > 1:
            do_grupo = [
                candidato
                for candidato in empatados
                if normalizar(geral[candidato].grupo) == normalizar(contato.grupo)
            ]
            if len(do_grupo) == 1:
                indice = do_grupo[0]
            else:
                nomes = " / ".join(nomes_geral[candidato] for candidato in empatados)
                relatorio.ambiguos.append(f"{contato.nome_contato} → {nomes}")

        if indice is None:
            relatorio.contato_sem_par.append(contato.nome_contato)
            contato.nome = contato.nome_contato
            relatorio.registros.append(contato)
            continue

        registro = geral[indice]
        usados.add(indice)
        registro.nome_contato = contato.nome_contato
        registro.data_bruta = contato.data_bruta
        registro.dia = contato.dia
        registro.mes = contato.mes
        registro.ano = contato.ano
        registro.tel_residencial = contato.tel_residencial
        registro.tel_comercial = contato.tel_comercial
        registro.celular = contato.celular
        registro.visitas = contato.visitas
        registro.problemas.extend(contato.problemas)
        relatorio.registros.append(registro)

    for indice, registro in enumerate(geral):
        if indice not in usados:
            relatorio.geral_sem_contato.append(registro.nome)
            relatorio.registros.append(registro)

    for registro in relatorio.registros:
        if not registro.mes or not registro.dia:
            relatorio.sem_aniversario.append(registro.nome)
        for problema in registro.problemas:
            relatorio.problemas.append(f"{registro.nome}: {problema}")
        for campo in ("tel_residencial", "tel_comercial", "celular"):
            bruto = getattr(registro, campo)
            if not bruto:
                continue
            normalizado = servico_pessoas.normalizar_telefone(bruto)
            if not _telefone_valido(normalizado):
                relatorio.telefones_suspeitos.append(
                    f"{registro.nome}: {bruto} ({campo})"
                )

    return relatorio


def _data_de(texto: str) -> Optional[date]:
    achado = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", (texto or "").strip())
    if not achado:
        return None
    dia, mes, ano = (int(parte) for parte in achado.groups())
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Aplicação no banco
# ---------------------------------------------------------------------------
def _telefone_valido(valor: str) -> bool:
    """O padrão do painel é `55` + DDD + número (12 ou 13 dígitos)."""
    return len(valor) in (12, 13) and valor.startswith("55")


def _nome_preferido(atual: str, novo: str) -> str:
    """Fica com o nome mais completo; abreviação (`C.`) não é completude."""
    if not novo:
        return atual
    if not atual:
        return novo

    def completude(nome: str) -> tuple[int, int, int]:
        tokens = _tokens(nome)
        inteiros = [token for token in tokens if len(token) > 1]
        iniciais = len(tokens) - len(inteiros)
        return (len(inteiros), sum(len(token) for token in inteiros), -iniciais)

    return novo if completude(novo) > completude(atual) else atual


def _telefone_principal(registro: Registro) -> str:
    for bruto in (registro.celular, registro.tel_residencial, registro.tel_comercial):
        if not bruto:
            continue
        normalizado = servico_pessoas.normalizar_telefone(bruto)
        if _telefone_valido(normalizado):
            return normalizado
    return ""


@dataclass
class Resultado:
    criados: int = 0
    atualizados: int = 0
    sem_par_no_banco: list[str] = field(default_factory=list)
    conflitos: list[str] = field(default_factory=list)
    nomes_alterados: list[str] = field(default_factory=list)
    telefones: int = 0
    visitas: int = 0

    def resumo(self) -> str:
        linhas = [
            f"Criados: {self.criados} | Atualizados: {self.atualizados}",
            f"Telefones preenchidos: {self.telefones} | "
            f"Últimas visitas: {self.visitas}",
        ]
        if self.sem_par_no_banco:
            linhas.append(f"Sem par no banco: {self.sem_par_no_banco}")
        if self.conflitos:
            linhas.append(f"Conflitos: {self.conflitos}")
        if self.nomes_alterados:
            linhas.append(f"Nomes completados: {self.nomes_alterados}")
        return "\n".join(linhas)


def aplicar(
    session: Session, relatorio: Relatorio, dry_run: bool = True
) -> Resultado:
    """Grava a junção na tabela `icm` preservando gênero/exclusão manuais."""
    existentes = list(session.exec(select(PessoaICM)).all())
    nomes_existentes = [pessoa.nome for pessoa in existentes]
    usados: set[int] = set()
    resultado = Resultado()

    for registro in relatorio.registros:
        indice, empatados = _melhor_par(registro.nomes, nomes_existentes, ignorar=usados)
        pessoa = existentes[indice] if indice is not None else None

        if pessoa is not None and len(empatados) > 1:
            resultado.conflitos.append(
                f"{registro.melhor_nome} → "
                + " / ".join(nomes_existentes[outro] for outro in empatados)
            )

        if pessoa is None:
            pessoa = PessoaICM(
                nome=registro.melhor_nome,
                nome_chave=servico_pessoas.normalizar_nome(registro.melhor_nome),
            )
            resultado.criados += 1
        else:
            usados.add(indice)
            nome_anterior = pessoa.nome
            nome_escolhido = _nome_preferido(pessoa.nome, registro.melhor_nome)
            if nome_escolhido != nome_anterior:
                resultado.nomes_alterados.append(f"{nome_anterior} → {nome_escolhido}")
                pessoa.nome = nome_escolhido
                pessoa.nome_chave = servico_pessoas.normalizar_nome(nome_escolhido)

            resultado.atualizados += 1

        if registro.grupo:
            pessoa.grupo = registro.grupo
        if registro.situacao:
            pessoa.situacao = registro.situacao
        if registro.categoria:
            pessoa.categoria = registro.categoria

        # Gênero é manual: só preenche quando está vazio.
        if not pessoa.genero and registro.sexo in ("M", "F"):
            pessoa.genero = registro.sexo

        # Aniversário: a planilha manda, mas divergência é reportada.
        if registro.dia and registro.mes:
            if pessoa.dia and pessoa.mes and (pessoa.dia, pessoa.mes) != (
                registro.dia,
                registro.mes,
            ):
                resultado.conflitos.append(
                    f"{pessoa.nome}: aniversário {pessoa.dia:02d}/{pessoa.mes:02d} "
                    f"→ {registro.dia:02d}/{registro.mes:02d}"
                )
            pessoa.dia = registro.dia
            pessoa.mes = registro.mes
        if registro.ano:
            pessoa.ano = registro.ano

        telefones = {
            "tel_residencial": servico_pessoas.normalizar_telefone(
                registro.tel_residencial
            ),
            "tel_comercial": servico_pessoas.normalizar_telefone(
                registro.tel_comercial
            ),
            "celular": servico_pessoas.normalizar_telefone(registro.celular),
        }
        for campo, valor in telefones.items():
            if _telefone_valido(valor) and getattr(pessoa, campo) != valor:
                setattr(pessoa, campo, valor)
                resultado.telefones += 1

        principal = _telefone_principal(registro)
        if principal and not pessoa.telefone:
            pessoa.telefone = principal

        if registro.visitas is not None:
            calculada = relatorio.referencia - timedelta(days=registro.visitas)
            # A visita registrada no painel é mais nova que o contador do PDF:
            # reimportar nunca faz a data andar para trás.
            if pessoa.ultima_visita is None or calculada > pessoa.ultima_visita:
                pessoa.ultima_visita = calculada
                pessoa.dias_sem_visita = registro.visitas
                pessoa.visitas_referencia = relatorio.referencia
                resultado.visitas += 1

        pessoa.ativo = True
        pessoa.visto_em = datetime.utcnow()
        pessoa.atualizado_em = datetime.utcnow()

        if not dry_run:
            session.add(pessoa)
            session.flush()

    resultado.sem_par_no_banco = [
        pessoa.nome for indice, pessoa in enumerate(existentes) if indice not in usados
    ]

    if dry_run:
        session.rollback()
    else:
        session.commit()

    return resultado


def contar_por_grupo(registros: Sequence[Registro]) -> dict[str, int]:
    return dict(Counter(registro.grupo for registro in registros))
