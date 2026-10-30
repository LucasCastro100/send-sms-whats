"""Regras compartilhadas pelos aniversariantes do ICM (PDF) e do Zoom (CSV)."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import urllib.parse

from dotenv import load_dotenv
import pandas as pd
from pypdf import PdfReader
import pytz
import requests
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "data"
PASTA_RUNTIME = RAIZ / "runtime"
PASTA_RUNTIME.mkdir(parents=True, exist_ok=True)

load_dotenv(RAIZ / ".env")

EVOLUTION_BASE_URL = os.getenv("EVOLUTION_BASE_URL", "https://evolution.ideiasdev.tech")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "igreja-bot")
EVOLUTION_APIKEY = os.getenv("EVOLUTION_APIKEY", "")

JID_GRUPO_IGREJA_FIXO = os.getenv("JID_GRUPO_IGREJA_FIXO", "553498018995-1503451609@g.us")
NOME_GRUPO_IGREJA_FIXO = os.getenv("NOME_GRUPO_IGREJA_FIXO", "ICM - IGREJA BOA VISTA")

JID_GRUPO_ZOOM = os.getenv("JID_GRUPO_ZOOM", "")
NOME_GRUPO_ZOOM = os.getenv("NOME_GRUPO_ZOOM", "Zoom")

ARQUIVO_PDF = PASTA_DADOS / "data.pdf"
ARQUIVO_ZOOM = PASTA_DADOS / "aniversariantes_zoom.csv"
ARQUIVO_GENEROS = PASTA_DADOS / "generos.json"
ARQUIVO_LOG = PASTA_RUNTIME / "aniversariantes.log"
FUSO = "America/Sao_Paulo"


def agora() -> datetime:
    """Data/hora atual em Brasília (o servidor/CI roda em UTC)."""
    return datetime.now(pytz.timezone(FUSO))

# Ícones usados nas mensagens (troque aqui se quiser outro emoji)
ICONE_ANIVERSARIANTE = "🥳"
ICONE_IRMA = "👧🎉"
ICONE_IRMAO = "👦🎉"

MESES_MAP = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


# ---------------------------------------------------------------------------
# Leitura dos dados
# ---------------------------------------------------------------------------
def parse_pdf(file_path: Path) -> pd.DataFrame:
    """Extrai e estrutura os aniversariantes do PDF do ICM (sem cache)."""
    if not file_path.exists():
        return pd.DataFrame()

    reader = PdfReader(file_path)
    padrao = r"^(\d+)\s+(\d{2}/\d{2})\s+(.+?)\s+(\d+\s*-.*)$"
    dados_estruturados = []

    for page in reader.pages:
        text = page.extract_text()
        if not text:
            continue

        for linha in text.splitlines():
            linha = linha.strip()
            match = re.match(padrao, linha)

            if match:
                data_nasc = match.group(2)
                _dia, mes = data_nasc.split("/")

                dados_estruturados.append(
                    {
                        "Número": int(match.group(1)),
                        "Data Nasc.": data_nasc,
                        "Mês_Num": int(mes),
                        "Nome": match.group(3),
                        "Grupo de Assistência": match.group(4),
                    }
                )

    return pd.DataFrame(dados_estruturados)


def parse_csv(file_path: Path) -> pd.DataFrame:
    """Lê a lista manual de aniversariantes (Nome, Data Nasc. em dd/mm)."""
    if not file_path.exists():
        return pd.DataFrame()

    df = pd.read_csv(file_path, dtype=str).fillna("")
    df.columns = [c.strip() for c in df.columns]

    if "Nome" not in df.columns or "Data Nasc." not in df.columns:
        return pd.DataFrame()

    df["Nome"] = df["Nome"].str.strip()
    df["Data Nasc."] = df["Data Nasc."].str.strip()
    df = df[(df["Nome"] != "") & df["Data Nasc."].str.match(r"^\d{2}/\d{2}$")].copy()

    if df.empty:
        return df

    df["Dia"] = df["Data Nasc."].str[:2].astype(int)
    df["Mês_Num"] = df["Data Nasc."].str[3:].astype(int)
    df["Mês"] = df["Mês_Num"].map(MESES_MAP)
    df["Número"] = range(1, len(df) + 1)

    # Ordena por ordem cronológica: mês e depois dia
    df = df.sort_values(["Mês_Num", "Dia", "Nome"]).reset_index(drop=True)
    df["Número"] = range(1, len(df) + 1)

    return df


@st.cache_data
def read_and_parse_pdf(file_path: Path) -> pd.DataFrame:
    """Versão com cache do PDF, usada apenas pela interface."""
    return parse_pdf(file_path)


@st.cache_data
def read_and_parse_csv(file_path: Path) -> pd.DataFrame:
    """Versão com cache do CSV, usada apenas pela interface."""
    return parse_csv(file_path)


# ---------------------------------------------------------------------------
# Gênero (irmão / irmã)
# ---------------------------------------------------------------------------
def _normalizar_nome(nome: str) -> str:
    return re.sub(r"\s+", " ", str(nome)).strip().upper()


def carregar_generos() -> dict[str, str]:
    """Lê o generos.json (nome completo ou primeiro nome -> "M" ou "F")."""
    try:
        with open(ARQUIVO_GENEROS, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    return {
        _normalizar_nome(nome): str(valor).strip().upper()[:1]
        for nome, valor in dados.items()
    }


def genero_de(nome: str, generos: dict[str, str] | None = None) -> str | None:
    """Retorna "M", "F" ou None (desconhecido) para o nome informado."""
    generos = carregar_generos() if generos is None else generos
    chave = _normalizar_nome(nome)

    if chave in generos:
        return generos[chave]

    primeiro_nome = chave.split()[0] if chave else ""
    if primeiro_nome in generos:
        return generos[primeiro_nome]

    return None


def nomes_sem_genero(df: pd.DataFrame) -> list[str]:
    """Lista os nomes do DataFrame que ainda não têm gênero cadastrado."""
    generos = carregar_generos()
    return sorted(
        {
            row["Nome"]
            for _, row in df.iterrows()
            if genero_de(row["Nome"], generos) is None
        }
    )


# ---------------------------------------------------------------------------
# Mensagem e envio
# ---------------------------------------------------------------------------
def enviar_via_evolution_api(texto: str, destinatario_jid: str) -> tuple[bool, str]:
    """Envia mensagem de texto via Evolution API."""
    url = f"{EVOLUTION_BASE_URL.rstrip('/')}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {
        "apikey": EVOLUTION_APIKEY,
        "Content-Type": "application/json",
    }

    destino = (destinatario_jid or "").strip()
    if not destino.endswith("@g.us"):
        destino = re.sub(r"\D", "", destino)

    payload = {
        "number": destino,
        "text": texto,
        "options": {"delay": 0, "presence": "composing", "linkPreview": False},
        "textMessage": {"text": texto},
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code in [200, 201]:
            return True, "Enviado com sucesso!"
        else:
            return False, f"Erro (Status {response.status_code}): {response.text}"
    except Exception as e:
        return False, f"Falha de conexão: {str(e)}"


def link_whatsapp(texto: str) -> str:
    return f"https://web.whatsapp.com/send?text={urllib.parse.quote(texto)}"


def montar_mensagem_aniversariantes(df_aniversariantes: pd.DataFrame, data_str: str) -> str:
    """Monta o texto da mensagem de parabéns para os aniversariantes do dia."""
    generos = carregar_generos()

    linhas_mensagem = []
    generos_do_dia = []
    for _, row in df_aniversariantes.iterrows():
        genero = genero_de(row["Nome"], generos)
        generos_do_dia.append(genero)
        icone = ICONE_IRMA if genero == "F" else ICONE_IRMAO

        # grupo = str(row.get("Grupo de Assistência", "") or "").strip()
        # complemento = f" ({grupo})" if grupo else ""
        # linhas_mensagem.append(f"• {icone} *{row['Nome']}*{complemento}")
        
        linhas_mensagem.append(f"• {icone} *{row['Nome']}*")

    if len(df_aniversariantes) == 1:
        # Um só aniversariante: fala com "você"
        if generos_do_dia[0] == "F":
            abertura = "Hoje é dia de comemorar a vida da nossa irmã"
        else:
            abertura = "Hoje é dia de comemorar a vida do nosso irmão"
        fechamento = (
            "Desejamos que o Senhor abençoe grandemente a sua vida! "
            "Parabéns! 🎂🎈"
        )
    elif all(genero == "F" for genero in generos_do_dia):
        # Várias pessoas, todas mulheres
        abertura = "Hoje é dia de comemorar a vida das nossas irmãs"
        fechamento = (
            "Desejamos que o Senhor abençoe grandemente a vida de cada uma! "
            "Parabéns! 🎂🎈"
        )
    else:
        # Vários homens ou grupo misto
        abertura = "Hoje é dia de comemorar a vida dos nossos irmãos"
        fechamento = (
            "Desejamos que o Senhor abençoe grandemente a vida de cada um! "
            "Parabéns! 🎂🎈"
        )

    return (
        f"🎉 *ANIVERSARIANTES DO DIA ({data_str})* 🎉\n\n"
        f"{abertura}: {ICONE_ANIVERSARIANTE}\n\n"
        + "\n".join(linhas_mensagem)
        + "\n\n"
        + fechamento
    )


def montar_mensagem_zoom(df_aniversariantes: pd.DataFrame, data_str: str) -> str:
    """Mensagem do Zoom: um parabéns nominal por aniversariante do dia."""
    generos = carregar_generos()

    linhas_mensagem = []
    for _, row in df_aniversariantes.iterrows():
        icone = ICONE_IRMA if genero_de(row["Nome"], generos) == "F" else ICONE_IRMAO
        linhas_mensagem.append(
            f"{icone} Parabéns, *{row['Nome']}*! "
            "Que o Senhor abençoe grandemente a sua vida! 🎂🎈"
        )

    return (
        f"🎉 *ANIVERSARIANTES DO DIA ({data_str})* 🎉\n\n"
        + "\n".join(linhas_mensagem)
    )


# ---------------------------------------------------------------------------
# Disparo automático (agendador)
# ---------------------------------------------------------------------------
def _registrar_log(mensagem: str) -> None:
    """Grava uma linha de log no console e no arquivo aniversariantes.log."""
    linha = f"[{agora().strftime('%Y-%m-%d %H:%M:%S')}] {mensagem}"
    print(linha, flush=True)
    try:
        with open(ARQUIVO_LOG, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except OSError:
        pass


def _disparar_do_dia(
    df: pd.DataFrame,
    origem: str,
    destino_jid: str,
    nome_grupo: str,
    montar_mensagem=montar_mensagem_aniversariantes,
    data_ref: str | None = None,
) -> tuple[bool, str]:
    hoje_str = data_ref or agora().strftime("%d/%m")

    if not destino_jid:
        aviso = (
            f"[{origem}] JID do grupo '{nome_grupo}' não configurado. "
            "Disparo cancelado."
        )
        _registrar_log(aviso)
        return False, aviso

    if df.empty:
        aviso = f"[{origem}] Lista de aniversariantes vazia ou não encontrada. Disparo cancelado."
        _registrar_log(aviso)
        return False, aviso

    df_hoje = df[df["Data Nasc."] == hoje_str]

    if df_hoje.empty:
        aviso = f"[{origem}] Nenhum aniversariante em {hoje_str}. Nada a enviar."
        _registrar_log(aviso)
        return True, aviso

    mensagem = montar_mensagem(df_hoje, hoje_str)
    sucesso, retorno = enviar_via_evolution_api(mensagem, destino_jid)

    nomes = ", ".join(df_hoje["Nome"].tolist())
    _registrar_log(
        f"[{origem}] Aniversariantes de {hoje_str}: {nomes} | "
        f"Envio para {nome_grupo}: {'OK' if sucesso else 'FALHA'} - {retorno}"
    )
    return sucesso, retorno


def disparar_aniversariantes_icm(data_ref: str | None = None) -> tuple[bool, str]:
    """Envia a mensagem dos aniversariantes do dia para o grupo do ICM."""
    try:
        return _disparar_do_dia(
            parse_pdf(ARQUIVO_PDF),
            origem="ICM",
            destino_jid=JID_GRUPO_IGREJA_FIXO,
            nome_grupo=NOME_GRUPO_IGREJA_FIXO,
            data_ref=data_ref,
        )
    except Exception as e:
        erro = f"[ICM] Erro inesperado no disparo automático: {str(e)}"
        _registrar_log(erro)
        return False, erro


def disparar_aniversariantes_zoom(data_ref: str | None = None) -> tuple[bool, str]:
    """Envia a mensagem dos aniversariantes do dia para o grupo do Zoom."""
    try:
        return _disparar_do_dia(
            parse_csv(ARQUIVO_ZOOM),
            origem="Zoom",
            destino_jid=JID_GRUPO_ZOOM,
            nome_grupo=NOME_GRUPO_ZOOM,
            montar_mensagem=montar_mensagem_zoom,
            data_ref=data_ref,
        )
    except Exception as e:
        erro = f"[Zoom] Erro inesperado no disparo automático: {str(e)}"
        _registrar_log(erro)
        return False, erro
