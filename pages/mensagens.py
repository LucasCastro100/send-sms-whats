import os
from datetime import datetime, timedelta
from pathlib import Path
import re
import sys

from dotenv import find_dotenv, load_dotenv
import requests
import streamlit as st

# Garante que os módulos compartilhados (raiz do projeto) sejam encontrados
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agendamentos import (  # noqa: E402
    agendar_envio,
    agora as agora_brt,
    cancelar_agendamento,
    ler_agendamentos,
)

# Carrega as variáveis do .env localizando a raiz do projeto
env_file = find_dotenv(usecwd=True)
if env_file:
    load_dotenv(dotenv_path=env_file, override=True)
else:
    base_dir = Path(__file__).resolve().parent.parent
    load_dotenv(dotenv_path=base_dir / ".env", override=True)

EVOLUTION_BASE_URL = os.getenv("EVOLUTION_BASE_URL", "https://evolution.ideiasdev.tech")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "igreja-bot")
EVOLUTION_APIKEY = os.getenv("EVOLUTION_APIKEY", "")

st.set_page_config(page_title="Envio de Mensagens", layout="wide")


def formatar_numero(jid_ou_numero: str) -> str:
    """Transforma 5534999998888 em +55 (34) 99999-8888 (quando possível)."""
    numeros = re.sub(r"\D", "", str(jid_ou_numero))
    if len(numeros) == 13:
        return f"+{numeros[:2]} ({numeros[2:4]}) {numeros[4:9]}-{numeros[9:]}"
    if len(numeros) == 12:
        return f"+{numeros[:2]} ({numeros[2:4]}) {numeros[4:8]}-{numeros[8:]}"
    return f"+{numeros}" if numeros else ""


@st.cache_data(ttl=600, show_spinner=False)
def buscar_grupos_whatsapp() -> dict:
    """Busca a lista de grupos na Evolution API com cache de 10 minutos."""
    url = f"{EVOLUTION_BASE_URL.rstrip('/')}/group/fetchAllGroups/{EVOLUTION_INSTANCE}?getParticipants=false"
    headers = {"apikey": EVOLUTION_APIKEY}
    grupos = {}

    try:
        response = requests.get(url, headers=headers, timeout=25)
        if response.status_code in [200, 201]:
            dados = response.json()
            if isinstance(dados, list):
                for item in dados:
                    jid = item.get("id")
                    nome = item.get("subject") or item.get("name")
                    if jid and jid.endswith("@g.us") and nome:
                        grupos[nome.strip()] = jid
    except Exception as e:
        st.sidebar.error(f"Erro ao buscar grupos: {str(e)}")

    return dict(sorted(grupos.items()))


@st.cache_data(ttl=600, show_spinner=False)
def buscar_contatos_whatsapp() -> dict:
    """Busca os contatos individuais (com número) na Evolution API."""
    url = f"{EVOLUTION_BASE_URL.rstrip('/')}/chat/findContacts/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_APIKEY, "Content-Type": "application/json"}
    contatos = {}

    try:
        response = requests.post(url, headers=headers, json={"where": {}}, timeout=30)
        if response.status_code in [200, 201]:
            dados = response.json()
            if isinstance(dados, list):
                for item in dados:
                    jid = (item.get("remoteJid") or "").strip()
                    if not jid.endswith("@s.whatsapp.net"):
                        continue
                    nome = (item.get("pushName") or "").strip()
                    if not nome:
                        nome = formatar_numero(jid)
                    contatos[jid] = nome
        else:
            st.sidebar.error(
                f"Erro ao buscar contatos (Status {response.status_code}): {response.text}"
            )
    except Exception as e:
        st.sidebar.error(f"Erro ao buscar contatos: {str(e)}")

    return dict(sorted(contatos.items(), key=lambda kv: kv[1].lower()))


def enviar_via_evolution_api(texto: str, destinatario_jid: str) -> tuple[bool, str]:
    """Envia mensagem de texto via Evolution API."""
    url = f"{EVOLUTION_BASE_URL.rstrip('/')}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {
        "apikey": EVOLUTION_APIKEY,
        "Content-Type": "application/json",
    }

    destino = destinatario_jid.strip()
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


def disparar_para_destinos(texto: str, destinos: list[tuple[str, str]]) -> None:
    """Envia o texto para cada (nome, jid) e mostra o progresso."""
    progresso = st.progress(0)
    status_container = st.container()

    sucessos = 0
    erros = 0
    total = len(destinos)

    for idx, (nome, jid) in enumerate(destinos):
        ok, msg = enviar_via_evolution_api(texto, jid)
        if ok:
            sucessos += 1
            status_container.success(f"✅ Enviado para **{nome}**")
        else:
            erros += 1
            status_container.error(f"❌ Falha ao enviar para **{nome}**: {msg}")

        progresso.progress((idx + 1) / total)

    if sucessos:
        st.balloons()
    st.success(
        f"Disparo concluído! {sucessos} enviado(s) com sucesso, {erros} falha(s)."
    )


# --- INTERFACE DA PÁGINA ---
st.title("💬 Envio de Mensagens Personalizadas")

if st.sidebar.button("🔄 Recarregar Grupos e Contatos"):
    st.cache_data.clear()

dict_grupos = buscar_grupos_whatsapp()
dict_contatos = buscar_contatos_whatsapp()

# Inicializa estado no session_state para salvar checkboxes marcados
if "selecao_grupos" not in st.session_state:
    st.session_state.selecao_grupos = {jid: False for jid in dict_grupos.values()}

st.subheader("1. Conteúdo da Mensagem")
texto_livre = st.text_area(
    "Digite a mensagem a ser enviada:",
    height=220,
    placeholder="Escreva aqui o aviso, comunicado ou lembrete...",
)

st.subheader("2. Destino")

aba_grupos, aba_conversas, aba_agendar = st.tabs(
    ["👥 Grupos", "💬 Conversas", "⏰ Agendar"]
)

# ---------------------------------------------------------------------------
# ABA GRUPOS
# ---------------------------------------------------------------------------
with aba_grupos:
    filtro_pesquisa = st.text_input(
        "🔍 Buscar grupo por nome:",
        placeholder="Digite para filtrar (ex: Obreiros, Boa Vista)...",
    )

    col_b1, col_b2 = st.columns(2)
    if col_b1.button("✅ Marcar Todos Visíveis", width="stretch"):
        for nome_g, jid_g in dict_grupos.items():
            if not filtro_pesquisa or filtro_pesquisa.lower() in nome_g.lower():
                st.session_state.selecao_grupos[jid_g] = True
        st.rerun()

    if col_b2.button("❌ Desmarcar Todos", width="stretch"):
        for jid_g in dict_grupos.values():
            st.session_state.selecao_grupos[jid_g] = False
        st.rerun()

    with st.container(height=240):
        for nome_grupo, jid_grupo in dict_grupos.items():
            if not filtro_pesquisa or filtro_pesquisa.lower() in nome_grupo.lower():
                estado_atual = st.session_state.selecao_grupos.get(jid_grupo, False)
                novo_estado = st.checkbox(
                    f"📌 {nome_grupo}",
                    value=estado_atual,
                    key=f"chk_state_{jid_grupo}",
                )
                st.session_state.selecao_grupos[jid_grupo] = novo_estado

    grupos_marcados = [
        {"nome": nome, "jid": jid}
        for nome, jid in dict_grupos.items()
        if st.session_state.selecao_grupos.get(jid, False)
    ]

    if grupos_marcados:
        st.markdown(f"**Grupos Selecionados ({len(grupos_marcados)}):**")
        st.dataframe(
            [{"Grupo": g["nome"], "Código (JID)": g["jid"]} for g in grupos_marcados],
            hide_index=True,
            width="stretch",
        )
        st.caption("Código(s) do(s) grupo(s) selecionado(s) — clique para copiar:")
        st.code("\n".join(g["jid"] for g in grupos_marcados))
    else:
        st.info("**Grupos Selecionados (0):** Nenhum")

    if st.button("🚀 Disparar para os Grupos Selecionados", width="stretch"):
        if not texto_livre.strip():
            st.warning("Por favor, digite o texto da mensagem antes de enviar.")
        elif not grupos_marcados:
            st.warning("Selecione pelo menos um grupo na lista de checkboxes.")
        else:
            disparar_para_destinos(
                texto_livre,
                [(g["nome"], g["jid"]) for g in grupos_marcados],
            )

# ---------------------------------------------------------------------------
# ABA CONVERSAS
# ---------------------------------------------------------------------------
with aba_conversas:
    st.caption(
        f"**{len(dict_contatos)} contatos com número** encontrados na instância "
        f"`{EVOLUTION_INSTANCE}`."
    )

    modo = st.radio(
        "Como escolher o destinatário?",
        ["Escolher da lista", "Digitar número"],
        horizontal=True,
    )

    if modo == "Escolher da lista":
        mapa_contatos = {
            f"{nome} — {formatar_numero(jid)}": jid
            for jid, nome in dict_contatos.items()
        }
        selecionados = st.multiselect(
            "🔍 Buscar e selecionar contatos:",
            options=sorted(mapa_contatos.keys()),
            placeholder="Digite um nome ou número...",
        )

        if selecionados:
            st.markdown(f"**Contatos Selecionados ({len(selecionados)}):**")
            st.dataframe(
                [
                    {
                        "Contato": rotulo.rsplit(" — ", 1)[0],
                        "Número": formatar_numero(mapa_contatos[rotulo]),
                    }
                    for rotulo in selecionados
                ],
                hide_index=True,
                width="stretch",
            )

        if st.button("🚀 Enviar para os Contatos Selecionados", width="stretch"):
            if not texto_livre.strip():
                st.warning("Por favor, digite o texto da mensagem antes de enviar.")
            elif not selecionados:
                st.warning("Selecione pelo menos um contato.")
            else:
                disparar_para_destinos(
                    texto_livre,
                    [
                        (rotulo.rsplit(" — ", 1)[0], mapa_contatos[rotulo])
                        for rotulo in selecionados
                    ],
                )

    else:
        col_num, col_nome = st.columns([1, 1])
        with col_num:
            numero_digitado = st.text_input(
                "Número (com DDI e DDD):",
                placeholder="+55 34 99999-9999",
            )
        with col_nome:
            nome_digitado = st.text_input(
                "Nome (opcional, só para o resumo):",
                placeholder="Ex: João",
            )

        numero_limpo = re.sub(r"\D", "", numero_digitado or "")

        if numero_digitado.strip():
            if 10 <= len(numero_limpo) <= 15:
                st.info(
                    f"Destino: **{nome_digitado.strip() or 'contato'}** — "
                    f"`{formatar_numero(numero_limpo)}`"
                )
            else:
                st.warning(
                    "Número incompleto. Use DDI + DDD + número "
                    "(ex.: 5534999998888)."
                )

        if st.button("🚀 Enviar para este Número", width="stretch"):
            if not texto_livre.strip():
                st.warning("Por favor, digite o texto da mensagem antes de enviar.")
            elif not (10 <= len(numero_limpo) <= 15):
                st.warning("Informe um número válido com DDI e DDD.")
            else:
                disparar_para_destinos(
                    texto_livre,
                    [(nome_digitado.strip() or formatar_numero(numero_limpo), numero_limpo)],
                )

# ---------------------------------------------------------------------------
# ABA AGENDAR
# ---------------------------------------------------------------------------
with aba_agendar:
    st.caption(
        "Agende um envio único, usando a mensagem do passo 1. "
        "O app precisa estar em execução no horário escolhido."
    )

    if st.session_state.pop("aviso_agendamento", None):
        st.success(st.session_state.get("mensagem_agendamento", "Envio agendado!"))

    tipo_destino = st.radio(
        "Destino do envio:",
        ["Número", "Grupo"],
        horizontal=True,
        key="agendar_tipo",
    )

    if tipo_destino == "Número":
        col_num_ag, col_nome_ag = st.columns(2)
        with col_num_ag:
            numero_ag = st.text_input(
                "Número (com DDI e DDD):",
                placeholder="+55 34 99999-9999",
                key="agendar_numero",
            )
        with col_nome_ag:
            nome_ag = st.text_input(
                "Nome (opcional):",
                placeholder="Ex: João",
                key="agendar_nome",
            )

        numero_ag_limpo = re.sub(r"\D", "", numero_ag or "")
        jid_ag = numero_ag_limpo
        nome_destino_ag = nome_ag.strip() or formatar_numero(numero_ag_limpo)

        if numero_ag.strip() and not (10 <= len(numero_ag_limpo) <= 15):
            st.warning("Número incompleto. Use DDI + DDD + número (ex.: 5534999998888).")

    else:
        if dict_grupos:
            grupo_ag = st.selectbox(
                "Grupo:",
                options=list(dict_grupos.keys()),
                key="agendar_grupo",
            )
            jid_ag = dict_grupos[grupo_ag]
            nome_destino_ag = grupo_ag
        else:
            jid_ag = ""
            nome_destino_ag = ""
            st.warning("Nenhum grupo encontrado para agendar.")

    col_data_ag, col_hora_ag = st.columns(2)
    with col_data_ag:
        data_ag = st.date_input(
            "Data do envio:",
            value=agora_brt().date(),
            key="agendar_data",
        )
    with col_hora_ag:
        hora_padrao = (agora_brt() + timedelta(hours=1)).replace(
            minute=0, second=0, microsecond=0
        )
        hora_ag = st.time_input(
            "Hora do envio (Brasília):",
            value=hora_padrao.time(),
            key="agendar_hora",
        )

    quando_ag = datetime.combine(data_ag, hora_ag)
    st.caption(f"⏰ Será enviado em **{quando_ag:%d/%m/%Y às %H:%M}**.")

    if st.button("⏰ Agendar envio", width="stretch", key="btn_agendar"):
        if not texto_livre.strip():
            st.warning("Por favor, digite o texto da mensagem no passo 1.")
        elif not jid_ag or not (10 <= len(jid_ag) <= 15):
            st.warning("Informe um número válido ou selecione um grupo.")
        elif quando_ag <= agora_brt().replace(tzinfo=None):
            st.warning("Escolha um horário no futuro.")
        else:
            item = agendar_envio(
                texto_livre, jid_ag, nome_destino_ag, quando_ag
            )
            st.session_state["aviso_agendamento"] = True
            st.session_state["mensagem_agendamento"] = (
                f"Envio agendado para **{item['nome']}** em "
                f"**{quando_ag:%d/%m/%Y às %H:%M}**."
            )
            st.rerun()

    st.markdown("---")
    st.subheader("📋 Envios agendados")

    agendamentos = ler_agendamentos()
    pendentes = [a for a in agendamentos if a.get("status") == "pendente"]

    if pendentes:
        st.dataframe(
            [
                {
                    "Destino": a.get("nome", ""),
                    "Quando": datetime.fromisoformat(a["quando"]).strftime(
                        "%d/%m/%Y %H:%M"
                    ),
                    "Mensagem": (a.get("texto", "")[:60] + "…")
                    if len(a.get("texto", "")) > 60
                    else a.get("texto", ""),
                }
                for a in pendentes
            ],
            hide_index=True,
            width="stretch",
        )

        mapa_cancelar = {
            f"{a['nome']} — {datetime.fromisoformat(a['quando']):%d/%m %H:%M}": a["id"]
            for a in pendentes
        }
        escolha_cancelar = st.selectbox(
            "Selecione para cancelar:",
            options=["—"] + list(mapa_cancelar.keys()),
            key="agendar_cancelar",
        )
        if st.button("🗑️ Cancelar agendamento", key="btn_cancelar") and escolha_cancelar != "—":
            cancelar_agendamento(mapa_cancelar[escolha_cancelar])
            st.rerun()
    else:
        st.info("Nenhum envio pendente no momento.")

    with st.expander("Histórico de envios agendados"):
        if agendamentos:
            st.dataframe(
                [
                    {
                        "Destino": a.get("nome", ""),
                        "Quando": datetime.fromisoformat(a["quando"]).strftime(
                            "%d/%m/%Y %H:%M"
                        ),
                        "Status": a.get("status", ""),
                        "Resultado": a.get("resultado", ""),
                    }
                    for a in reversed(agendamentos)
                ],
                hide_index=True,
                width="stretch",
            )
        else:
            st.caption("Nada por aqui ainda.")
