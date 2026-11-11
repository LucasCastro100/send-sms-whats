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

from core.evolution import (  # noqa: E402
    EVOLUTION_BASE_URL,
    EVOLUTION_INSTANCE,
    chave_api,
)

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "data"
PASTA_RUNTIME = RAIZ / "runtime"
PASTA_RUNTIME.mkdir(parents=True, exist_ok=True)

load_dotenv(RAIZ / ".env")

JID_GRUPO_IGREJA_FIXO = os.getenv("JID_GRUPO_IGREJA_FIXO", "553498018995-1503451609@g.us")
NOME_GRUPO_IGREJA_FIXO = os.getenv("NOME_GRUPO_IGREJA_FIXO", "ICM - IGREJA BOA VISTA")

JID_GRUPO_ZOOM = os.getenv("JID_GRUPO_ZOOM", "")
NOME_GRUPO_ZOOM = os.getenv("NOME_GRUPO_ZOOM", "Zoom")

ARQUIVO_PDF = PASTA_DADOS / "data.pdf"
ARQUIVO_ZOOM = PASTA_DADOS / "aniversariantes_zoom.csv"
ARQUIVO_GENEROS = PASTA_DADOS / "generos.json"
ARQUIVO_EXCLUSOES = PASTA_DADOS / "exclusoes.json"
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


# ---------------------------------------------------------------------------
# Gênero (irmão / irmã)
# ---------------------------------------------------------------------------
def _normalizar_nome(nome: str) -> str:
    return re.sub(r"\s+", " ", str(nome)).strip().upper()


def _normalizar_generos(dados: dict) -> dict[str, str]:
    """Normaliza um bloco {nome: "m"/"f"} para chaves maiúsculas."""
    return {
        _normalizar_nome(nome): str(valor).strip().upper()[:1]
        for nome, valor in dados.items()
        if str(nome).strip() and str(valor).strip()
    }


def carregar_generos(fonte: str | None = None) -> dict[str, str]:
    """Lê o generos.json, separado por fonte: {"icm": {...}, "zoom": {...}}.

    - `carregar_generos()`        -> junta ICM + Zoom (visão geral)
    - `carregar_generos("icm")`   -> só os nomes do ICM
    - `carregar_generos("zoom")`  -> só os nomes do Zoom

    O formato antigo (um único dicionário plano) continua sendo aceito.
    """
    try:
        with open(ARQUIVO_GENEROS, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(dados, dict):
        return {}

    separado = any(isinstance(valor, dict) for valor in dados.values())

    if not separado:
        # Formato antigo: {"NOME": "M", ...}
        return _normalizar_generos(dados)

    if fonte is None:
        juntos: dict[str, str] = {}
        for chave in ("icm", "zoom"):
            juntos.update(_normalizar_generos(dados.get(chave, {})))
        return juntos

    return _normalizar_generos(dados.get(fonte.lower(), {}))


def genero_de(
    nome: str,
    generos: dict[str, str] | None = None,
    fonte: str | None = None,
) -> str | None:
    """Retorna "M", "F" ou None (desconhecido) para o nome informado."""
    generos = carregar_generos(fonte) if generos is None else generos
    chave = _normalizar_nome(nome)

    if chave in generos:
        return generos[chave]

    primeiro_nome = chave.split()[0] if chave else ""
    if primeiro_nome in generos:
        return generos[primeiro_nome]

    return None


def nomes_sem_genero(df: pd.DataFrame, fonte: str | None = None) -> list[str]:
    """Lista os nomes do DataFrame que ainda não têm gênero cadastrado."""
    generos = carregar_generos(fonte)
    return sorted(
        {
            row["Nome"]
            for _, row in df.iterrows()
            if genero_de(row["Nome"], generos) is None
        }
    )


# ---------------------------------------------------------------------------
# Exclusões (quem NÃO deve ser citado nas mensagens)
# ---------------------------------------------------------------------------
def carregar_exclusoes() -> dict[str, list[str]]:
    """Lê exclusoes.json no formato {"icm": [...], "zoom": [...]}.

    Os nomes são guardados normalizados (maiúsculas, sem espaços repetidos),
    igual ao generos.json. O arquivo fica em `data/` para que o GitHub Actions
    também enxergue a lista.
    """
    vazio = {"icm": [], "zoom": []}
    try:
        with open(ARQUIVO_EXCLUSOES, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, json.JSONDecodeError):
        return vazio

    if not isinstance(dados, dict):
        return vazio

    return {
        fonte: sorted(
            {
                _normalizar_nome(nome)
                for nome in dados.get(fonte, [])
                if str(nome).strip()
            }
        )
        for fonte in ("icm", "zoom")
    }


def _gravar_exclusoes(dados: dict[str, list[str]]) -> None:
    ARQUIVO_EXCLUSOES.parent.mkdir(parents=True, exist_ok=True)
    with open(ARQUIVO_EXCLUSOES, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
        f.write("\n")


def nomes_excluidos(fonte: str) -> set[str]:
    """Nomes (normalizados) marcados para não receber, na fonte icm/zoom."""
    return set(carregar_exclusoes().get(fonte.lower(), []))


def esta_excluido(nome: str, fonte: str) -> bool:
    """Diz se a pessoa está marcada para não ser citada na mensagem."""
    return _normalizar_nome(nome) in nomes_excluidos(fonte)


def remover_excluidos(df: pd.DataFrame, fonte: str) -> pd.DataFrame:
    """Devolve o DataFrame sem as pessoas marcadas para não receber."""
    if df.empty:
        return df

    excluidos = nomes_excluidos(fonte)
    if not excluidos:
        return df

    return df[~df["Nome"].map(lambda nome: _normalizar_nome(nome) in excluidos)]


def atualizar_exclusoes(
    fonte: str,
    nomes_visiveis: list[str],
    nomes_bloqueados: list[str],
) -> list[str]:
    """Atualiza só os nomes visíveis na tela, preservando o resto do arquivo.

    Sem isso, salvar com um filtro de mês ativo apagaria as marcações feitas
    em outros meses.
    """
    dados = carregar_exclusoes()
    fonte = fonte.lower()

    visiveis = {_normalizar_nome(n) for n in nomes_visiveis if str(n).strip()}
    bloqueados = {_normalizar_nome(n) for n in nomes_bloqueados if str(n).strip()}
    atuais = set(dados.get(fonte, []))

    dados[fonte] = sorted((atuais - visiveis) | (bloqueados & visiveis))
    _gravar_exclusoes(dados)
    return dados[fonte]


# ---------------------------------------------------------------------------
# Mensagem e envio
# ---------------------------------------------------------------------------
def instancia_ativa() -> str:
    """Instância usada pelos scripts (a mesma do .env)."""
    return EVOLUTION_INSTANCE


def enviar_via_evolution_api(
    texto: str,
    destinatario_jid: str,
    instancia: str | None = None,
) -> tuple[bool, str]:
    """Envia mensagem de texto via Evolution API.

    Sem `instancia`, usa a instância do usuário logado (ou a padrão).
    """
    instancia = instancia or instancia_ativa()
    url = f"{EVOLUTION_BASE_URL.rstrip('/')}/message/sendText/{instancia}"
    headers = {
        "apikey": chave_api(instancia),
        "Content-Type": "application/json",
    }

    if not headers["apikey"]:
        return False, (
            f"Sem chave para a instância `{instancia}`. "
            "Configure `EVOLUTION_GLOBAL_APIKEY` ou use a instância padrão."
        )

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


def montar_mensagem_aniversariantes(
    df_aniversariantes: pd.DataFrame,
    data_str: str,
    fonte: str = "icm",
) -> str:
    """Monta o texto da mensagem de parabéns para os aniversariantes do dia."""
    generos = carregar_generos(fonte)

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


def montar_mensagem_zoom(
    df_aniversariantes: pd.DataFrame,
    data_str: str,
    fonte: str = "zoom",
) -> str:
    """Mensagem do Zoom: um parabéns nominal por aniversariante do dia."""
    generos = carregar_generos(fonte)

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

    # Respeita a lista de "não citar" salva em data/exclusoes.json
    excluidos = [
        nome for nome in df_hoje["Nome"] if esta_excluido(nome, origem.lower())
    ]
    df_hoje = remover_excluidos(df_hoje, origem.lower())

    if df_hoje.empty:
        aviso = (
            f"[{origem}] Aniversariantes de {hoje_str} todos marcados para NÃO "
            f"receber ({', '.join(excluidos)}). Nada a enviar."
        )
        _registrar_log(aviso)
        return True, aviso

    mensagem = montar_mensagem(df_hoje, hoje_str, fonte=origem.lower())
    # O disparo automático sempre usa a instância fixa do servidor/CI,
    # independentemente de quem estiver logado no painel.
    sucesso, retorno = enviar_via_evolution_api(
        mensagem, destino_jid, instancia=EVOLUTION_INSTANCE
    )

    nomes = ", ".join(df_hoje["Nome"].tolist())
    if excluidos:
        nomes += f" | Não citados: {', '.join(excluidos)}"
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
