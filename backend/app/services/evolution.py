"""Cliente da Evolution API (instâncias, QR, grupos e contatos)."""

from __future__ import annotations

import base64
import re
from typing import Optional
from urllib.parse import quote

import requests

from ..config import settings

TIMEOUT = 30
# A listagem de grupos é pesada na Evolution e costuma passar de 30s.
TIMEOUT_GRUPOS = 90


# ---------------------------------------------------------------------------
# Chaves e nomes
# ---------------------------------------------------------------------------
def tem_chave_global() -> bool:
    return bool(settings.evolution_global_apikey.strip())


def chave_api(instancia: Optional[str] = None) -> str:
    if tem_chave_global():
        return settings.evolution_global_apikey.strip()
    if not instancia or instancia == settings.evolution_instance:
        return settings.evolution_apikey.strip()
    return ""


def _headers(instancia: Optional[str] = None) -> dict:
    return {
        "apikey": chave_api(instancia),
        "Content-Type": "application/json",
    }


def _url(caminho: str) -> str:
    return f"{settings.evolution_base_url.rstrip('/')}{caminho}"


def slug(texto: str) -> str:
    import unicodedata

    sem_acento = (
        unicodedata.normalize("NFKD", str(texto))
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    resultado = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento).strip("-").lower()
    return resultado or "usuario"


def nome_instancia(usuario: str) -> str:
    return f"{settings.evolution_instance_prefix}{slug(usuario)}"


def formatar_numero(jid_ou_numero: str) -> str:
    numeros = re.sub(r"\D", "", str(jid_ou_numero))
    if len(numeros) == 13:
        return f"+{numeros[:2]} ({numeros[2:4]}) {numeros[4:9]}-{numeros[9:]}"
    if len(numeros) == 12:
        return f"+{numeros[:2]} ({numeros[2:4]}) {numeros[4:8]}-{numeros[8:]}"
    return f"+{numeros}" if numeros else ""


# ---------------------------------------------------------------------------
# Instâncias
# ---------------------------------------------------------------------------
def listar_instancias() -> list:
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


def info_instancia(instancia: str) -> Optional[dict]:
    for item in listar_instancias():
        if not isinstance(item, dict):
            continue
        if item.get("name") == instancia or item.get("instanceName") == instancia:
            return item
        bloco = item.get("instance")
        if isinstance(bloco, dict) and (
            bloco.get("name") == instancia
            or bloco.get("instanceName") == instancia
        ):
            return item
    return None


def resumo_instancias() -> dict:
    """`{nome: {estado, perfil, numero, jid}}` numa única chamada."""
    resumo: dict = {}

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
        numero = formatar_numero(jid) or formatar_numero(bloco.get("number") or "")

        resumo[str(nome)] = {
            "estado": str(estado_conexao),
            "perfil": str(bloco.get("profileName") or item.get("profileName") or ""),
            "numero": numero,
            "jid": str(jid),
        }

    return resumo


def estado(instancia: str) -> str:
    """`open`, `connecting`, `close`, `nao_existe`, `sem_chave` ou `erro`."""
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


def criar_instancia(instancia: str) -> tuple:
    if not tem_chave_global():
        return False, (
            "Para criar uma instância nova é preciso configurar "
            "`EVOLUTION_GLOBAL_APIKEY` (chave global da Evolution API)."
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
    if resposta.status_code == 403 and "already" in texto.lower():
        return True, {"ja_existia": True}
    if resposta.status_code == 401:
        return False, "Chave global recusada (401). Confira `EVOLUTION_GLOBAL_APIKEY`."

    return False, f"Erro ao criar instância (Status {resposta.status_code}): {texto}"


def conectar(instancia: str) -> tuple:
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
        return False, (
            f"Erro ao gerar QR Code (Status {resposta.status_code}): {resposta.text}"
        )

    try:
        return True, resposta.json()
    except ValueError:
        return False, "A Evolution API não retornou um JSON válido."


def desconectar(instancia: str) -> tuple:
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


# ---------------------------------------------------------------------------
# QR Code
# ---------------------------------------------------------------------------
def extrair_qr(dados: Optional[dict]) -> tuple:
    """Separa `(base64, código)` da resposta de create/connect."""
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


def qr_data_url(valor: Optional[str]) -> Optional[str]:
    """Garante o prefixo `data:image/png;base64,` para usar em `<img>`."""
    if not valor:
        return None

    texto = str(valor).strip()
    if texto.startswith("data:"):
        return texto

    try:
        base64.b64decode(texto)
    except Exception:
        return None
    return f"data:image/png;base64,{texto}"


# ---------------------------------------------------------------------------
# Mensagens
# ---------------------------------------------------------------------------
def enviar_texto(instancia: str, destino: str, texto: str) -> tuple:
    """Envia texto para um grupo (`@g.us`) ou número."""
    if not chave_api(instancia):
        return False, (
            f"Sem chave para a instância `{instancia}`. Configure "
            "`EVOLUTION_GLOBAL_APIKEY` ou use a instância padrão."
        )

    alvo = (destino or "").strip()
    if not alvo.endswith("@g.us"):
        alvo = re.sub(r"\D", "", alvo)
    if not alvo:
        return False, "Destino não configurado."

    payload = {
        "number": alvo,
        "text": texto,
        "options": {"delay": 0, "presence": "composing", "linkPreview": False},
        "textMessage": {"text": texto},
    }

    try:
        resposta = requests.post(
            _url(f"/message/sendText/{quote(instancia, safe='')}"),
            json=payload,
            headers=_headers(instancia),
            timeout=TIMEOUT,
        )
    except Exception as e:
        return False, f"Falha de conexão: {e}"

    if resposta.status_code in (200, 201):
        return True, "Enviado com sucesso!"
    return False, f"Erro (Status {resposta.status_code}): {resposta.text}"


# ---------------------------------------------------------------------------
# Grupos e contatos
# ---------------------------------------------------------------------------
def buscar_grupos(instancia: str) -> tuple:
    if not chave_api(instancia):
        return {}, "Sem chave para esta instância."

    try:
        resposta = requests.get(
            _url(
                f"/group/fetchAllGroups/{quote(instancia, safe='')}"
                "?getParticipants=false"
            ),
            headers=_headers(instancia),
            timeout=TIMEOUT_GRUPOS,
        )
    except Exception as e:
        return {}, f"Falha de conexão: {e}"

    if resposta.status_code not in (200, 201):
        return {}, (
            f"Erro ao buscar grupos (Status {resposta.status_code}): {resposta.text}"
        )

    try:
        dados = resposta.json()
    except ValueError:
        return {}, "A Evolution API não retornou um JSON válido."

    grupos: dict = {}
    if isinstance(dados, list):
        for item in dados:
            jid = item.get("id")
            nome = item.get("subject") or item.get("name")
            if jid and str(jid).endswith("@g.us") and nome:
                grupos[str(nome).strip()] = str(jid)

    return dict(sorted(grupos.items())), None


def buscar_contatos(instancia: str) -> tuple:
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
            f"Erro ao buscar contatos (Status {resposta.status_code}): {resposta.text}"
        )

    try:
        dados = resposta.json()
    except ValueError:
        return {}, "A Evolution API não retornou um JSON válido."

    contatos: dict = {}
    if isinstance(dados, list):
        for item in dados:
            jid = (item.get("remoteJid") or "").strip()
            if not jid.endswith("@s.whatsapp.net"):
                continue
            nome = (item.get("pushName") or "").strip() or formatar_numero(jid)
            contatos[jid] = nome

    return dict(sorted(contatos.items(), key=lambda kv: kv[1].lower())), None
