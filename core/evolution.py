"""Cliente da Evolution API: instâncias, QR Code, grupos e contatos.

A Evolution API é quem mantém a sessão do WhatsApp. Cada instância é um
"aparelho conectado" e tem o seu próprio QR Code, grupos e contatos.

- `EVOLUTION_APIKEY`        -> token de uma instância (funciona só para ela)
- `EVOLUTION_GLOBAL_APIKEY` -> chave mestre do servidor (necessária para criar
                               instâncias novas, uma por usuário)
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
import re
from urllib.parse import quote

from dotenv import load_dotenv
import requests

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

EVOLUTION_BASE_URL = os.getenv(
    "EVOLUTION_BASE_URL", "https://evolution.ideiasdev.tech"
).rstrip("/")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "igreja-bot")
EVOLUTION_APIKEY = os.getenv("EVOLUTION_APIKEY", "")
EVOLUTION_GLOBAL_APIKEY = os.getenv("EVOLUTION_GLOBAL_APIKEY", "")
EVOLUTION_INSTANCE_PREFIX = os.getenv("EVOLUTION_INSTANCE_PREFIX", "cb-")

TIMEOUT = 30


# ---------------------------------------------------------------------------
# Chaves e nomes
# ---------------------------------------------------------------------------
def tem_chave_global() -> bool:
    """Diz se a chave mestre do servidor está configurada."""
    return bool(EVOLUTION_GLOBAL_APIKEY.strip())


def chave_api(instancia: str | None = None) -> str:
    """Chave usada nas chamadas.

    Com a chave global, ela serve para qualquer instância. Sem ela, só o token
    da instância padrão (`EVOLUTION_INSTANCE`) funciona.
    """
    if tem_chave_global():
        return EVOLUTION_GLOBAL_APIKEY.strip()
    if not instancia or instancia == EVOLUTION_INSTANCE:
        return EVOLUTION_APIKEY.strip()
    return ""


def _headers(instancia: str | None = None) -> dict[str, str]:
    return {
        "apikey": chave_api(instancia),
        "Content-Type": "application/json",
    }


def _url(caminho: str) -> str:
    return f"{EVOLUTION_BASE_URL}{caminho}"


def slug(texto: str) -> str:
    """Transforma um nome em algo seguro para nome de instância."""
    import unicodedata

    sem_acento = (
        unicodedata.normalize("NFKD", str(texto))
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    resultado = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento).strip("-").lower()
    return resultado or "usuario"


def nome_instancia(usuario: str) -> str:
    """Nome da instância de um usuário (ex.: `cb-lucas`)."""
    return f"{EVOLUTION_INSTANCE_PREFIX}{slug(usuario)}"


def formatar_numero(jid_ou_numero: str) -> str:
    """Transforma 5534999998888 em +55 (34) 99999-8888 (quando possível)."""
    numeros = re.sub(r"\D", "", str(jid_ou_numero))
    if len(numeros) == 13:
        return f"+{numeros[:2]} ({numeros[2:4]}) {numeros[4:9]}-{numeros[9:]}"
    if len(numeros) == 12:
        return f"+{numeros[:2]} ({numeros[2:4]}) {numeros[4:8]}-{numeros[8:]}"
    return f"+{numeros}" if numeros else ""


# ---------------------------------------------------------------------------
# Instâncias
# ---------------------------------------------------------------------------
def listar_instancias() -> list[dict]:
    """Lista as instâncias do servidor (vazio se a chave não permitir)."""
    try:
        resposta = requests.get(
            _url("/instance/fetchInstances"),
            headers=_headers(),
            timeout=TIMEOUT,
        )
    except Exception:
        return []

    if resposta.status_code not in (200, 201):
        return []

    try:
        dados = resposta.json()
    except ValueError:
        return []

    return dados if isinstance(dados, list) else []


def info_instancia(instancia: str) -> dict | None:
    """Dados da instância (nome do perfil, número, status...)."""
    for item in listar_instancias():
        if item.get("name") == instancia or item.get("instanceName") == instancia:
            return item
    return None


def resumo_instancias() -> dict[str, dict]:
    """Status resumido de todas as instâncias, numa única chamada.

    Retorna `{nome: {"estado", "perfil", "numero", "jid"}}`. A resposta da
    Evolution API varia entre versões (objeto plano ou aninhado em
    `instance`), então os dois formatos são aceitos.
    """
    resumo: dict[str, dict] = {}

    for item in listar_instancias():
        if not isinstance(item, dict):
            continue

        bloco = item.get("instance")
        if not isinstance(bloco, dict):
            bloco = item

        nome = (
            bloco.get("instanceName")
            or bloco.get("name")
            or item.get("name")
            or item.get("instanceName")
        )
        if not nome:
            continue

        estado_conexao = (
            bloco.get("state")
            or bloco.get("status")
            or item.get("connectionStatus")
            or item.get("state")
            or "close"
        )
        jid = (
            item.get("ownerJid")
            or bloco.get("owner")
            or bloco.get("ownerJid")
            or ""
        )
        numero = formatar_numero(jid) or formatar_numero(
            bloco.get("number") or ""
        )

        resumo[str(nome)] = {
            "estado": str(estado_conexao),
            "perfil": str(bloco.get("profileName") or item.get("profileName") or ""),
            "numero": numero,
            "jid": str(jid),
        }

    return resumo


def estado(instancia: str) -> str:
    """Estado da conexão.

    Retornos possíveis: `open` (conectado), `connecting` (aguardando QR),
    `close` (desconectado), `nao_existe`, `sem_chave` ou `erro`.
    """
    if not instancia:
        return "nao_existe"

    if not chave_api(instancia):
        return "sem_chave"

    try:
        resposta = requests.get(
            _url(f"/instance/connectionState/{quote(instancia, safe='')}"),
            headers=_headers(instancia),
            timeout=TIMEOUT,
        )
    except Exception:
        return "erro"

    if resposta.status_code == 404:
        return "nao_existe"
    if resposta.status_code == 401:
        return "sem_chave"
    if resposta.status_code not in (200, 201):
        return "erro"

    try:
        dados = resposta.json()
    except ValueError:
        return "erro"

    bloco = dados.get("instance") if isinstance(dados, dict) else None
    if isinstance(bloco, dict) and bloco.get("state"):
        return str(bloco["state"])
    if isinstance(dados, dict) and dados.get("state"):
        return str(dados["state"])
    return "close"


def criar_instancia(instancia: str) -> tuple[bool, dict | str]:
    """Cria uma instância nova. Exige a chave global do servidor."""
    if not tem_chave_global():
        return False, (
            "Para criar uma instância nova é preciso configurar "
            "`EVOLUTION_GLOBAL_APIKEY` (chave global da Evolution API). "
            "Sem ela, só é possível reconectar a instância padrão."
        )

    payload = {
        "instanceName": instancia,
        "qrcode": True,
        "integration": "WHATSAPP-BAILEYS",
    }

    try:
        resposta = requests.post(
            _url("/instance/create"),
            json=payload,
            headers=_headers(),
            timeout=TIMEOUT,
        )
    except Exception as e:
        return False, f"Falha de conexão: {e}"

    if resposta.status_code in (200, 201):
        try:
            return True, resposta.json()
        except ValueError:
            return True, {}

    texto = resposta.text or ""

    # A instância já existe: segue para a conexão/QR em vez de falhar.
    if resposta.status_code == 403 and "already" in texto.lower():
        return True, {"ja_existia": True}

    if resposta.status_code == 401:
        return False, (
            "Chave global recusada (401). Confira `EVOLUTION_GLOBAL_APIKEY`."
        )

    return False, f"Erro ao criar instância (Status {resposta.status_code}): {texto}"


def conectar(instancia: str) -> tuple[bool, dict | str]:
    """Pede o QR Code (ou confirma que a instância já está conectada)."""
    if not chave_api(instancia):
        return False, (
            "Sem chave para esta instância. Configure `EVOLUTION_GLOBAL_APIKEY` "
            "ou use a instância padrão."
        )

    try:
        resposta = requests.get(
            _url(f"/instance/connect/{quote(instancia, safe='')}"),
            headers=_headers(instancia),
            timeout=TIMEOUT,
        )
    except Exception as e:
        return False, f"Falha de conexão: {e}"

    if resposta.status_code == 404:
        return False, f"A instância `{instancia}` não existe. Crie-a primeiro."
    if resposta.status_code == 401:
        return False, "Chave recusada (401). Confira as chaves da Evolution API."
    if resposta.status_code not in (200, 201):
        return False, f"Erro ao gerar QR Code (Status {resposta.status_code}): {resposta.text}"

    try:
        return True, resposta.json()
    except ValueError:
        return False, "A Evolution API não retornou um JSON válido."


def desconectar(instancia: str) -> tuple[bool, str]:
    """Desconecta o WhatsApp da instância (mantém a instância criada)."""
    if not chave_api(instancia):
        return False, "Sem chave para esta instância."

    try:
        resposta = requests.delete(
            _url(f"/instance/logout/{quote(instancia, safe='')}"),
            headers=_headers(instancia),
            timeout=TIMEOUT,
        )
    except Exception as e:
        return False, f"Falha de conexão: {e}"

    if resposta.status_code in (200, 201):
        return True, "WhatsApp desconectado."
    return False, f"Erro ao desconectar (Status {resposta.status_code}): {resposta.text}"


def deletar(instancia: str) -> tuple[bool, str]:
    """Apaga a instância do servidor (remove a sessão e os dados dela)."""
    if not tem_chave_global():
        return False, "Para apagar uma instância é preciso a chave global."

    try:
        resposta = requests.delete(
            _url(f"/instance/delete/{quote(instancia, safe='')}"),
            headers=_headers(),
            timeout=TIMEOUT,
        )
    except Exception as e:
        return False, f"Falha de conexão: {e}"

    if resposta.status_code in (200, 201):
        return True, "Instância apagada."
    return False, f"Erro ao apagar (Status {resposta.status_code}): {resposta.text}"


# ---------------------------------------------------------------------------
# QR Code
# ---------------------------------------------------------------------------
def extrair_qr(dados: dict | None) -> tuple[str | None, str | None]:
    """Separa (base64, código) da resposta de create/connect."""
    if not isinstance(dados, dict):
        return None, None

    bloco = dados.get("qrcode")
    if not isinstance(bloco, dict):
        bloco = dados

    base64_img = bloco.get("base64") or dados.get("base64")
    codigo = (
        bloco.get("code")
        or dados.get("code")
        or dados.get("pairingCode")
        or bloco.get("pairingCode")
    )
    return base64_img, codigo


def qr_bytes(valor: str | None) -> bytes | None:
    """Converte o base64 do QR (com ou sem prefixo data:) em bytes de imagem."""
    if not valor:
        return None

    texto = str(valor).strip()
    if texto.startswith("data:"):
        texto = texto.split(",", 1)[-1]

    try:
        return base64.b64decode(texto)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Grupos e contatos da instância
# ---------------------------------------------------------------------------
def buscar_grupos(instancia: str) -> tuple[dict[str, str], str | None]:
    """Grupos do WhatsApp conectado: {nome: jid}."""
    if not chave_api(instancia):
        return {}, "Sem chave para esta instância."

    try:
        resposta = requests.get(
            _url(
                f"/group/fetchAllGroups/{quote(instancia, safe='')}"
                "?getParticipants=false"
            ),
            headers=_headers(instancia),
            timeout=TIMEOUT,
        )
    except Exception as e:
        return {}, f"Falha de conexão: {e}"

    if resposta.status_code not in (200, 201):
        return {}, f"Erro ao buscar grupos (Status {resposta.status_code}): {resposta.text}"

    try:
        dados = resposta.json()
    except ValueError:
        return {}, "A Evolution API não retornou um JSON válido."

    grupos: dict[str, str] = {}
    if isinstance(dados, list):
        for item in dados:
            jid = item.get("id")
            nome = item.get("subject") or item.get("name")
            if jid and str(jid).endswith("@g.us") and nome:
                grupos[str(nome).strip()] = str(jid)

    return dict(sorted(grupos.items())), None


def buscar_contatos(instancia: str) -> tuple[dict[str, str], str | None]:
    """Contatos individuais do WhatsApp conectado: {jid: nome}."""
    if not chave_api(instancia):
        return {}, "Sem chave para esta instância."

    try:
        resposta = requests.post(
            _url(f"/chat/findContacts/{quote(instancia, safe='')}"),
            headers=_headers(instancia),
            json={"where": {}},
            timeout=TIMEOUT,
        )
    except Exception as e:
        return {}, f"Falha de conexão: {e}"

    if resposta.status_code not in (200, 201):
        return {}, (
            f"Erro ao buscar contatos (Status {resposta.status_code}): "
            f"{resposta.text}"
        )

    try:
        dados = resposta.json()
    except ValueError:
        return {}, "A Evolution API não retornou um JSON válido."

    contatos: dict[str, str] = {}
    if isinstance(dados, list):
        for item in dados:
            jid = (item.get("remoteJid") or "").strip()
            if not jid.endswith("@s.whatsapp.net"):
                continue
            nome = (item.get("pushName") or "").strip() or formatar_numero(jid)
            contatos[jid] = nome

    return dict(sorted(contatos.items(), key=lambda kv: kv[1].lower())), None
