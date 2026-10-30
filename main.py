import os
from pathlib import Path
from dotenv import find_dotenv, load_dotenv
import streamlit as st

# Carrega as variáveis de ambiente (.env local ou Secrets na nuvem)
env_file = find_dotenv(usecwd=True)
if env_file:
    load_dotenv(dotenv_path=env_file, override=True)
else:
    base_dir = Path(__file__).resolve().parent
    load_dotenv(dotenv_path=base_dir / ".env", override=True)

# Destinos exibidos no painel
from core.comum import (  # noqa: E402
    JID_GRUPO_IGREJA_FIXO,
    JID_GRUPO_ZOOM,
    NOME_GRUPO_IGREJA_FIXO,
    NOME_GRUPO_ZOOM,
)
from core.agendamentos import obter_agendador  # noqa: E402


def inicializar_agendador_cron():
    """Agendador do app: apenas os envios avulsos agendados na página Mensagens.

    O disparo diário dos aniversariantes NÃO fica aqui: quem faz isso é o
    GitHub Actions (`.github/workflows/disparo-diario.yml`), às 00:00 de
    Brasília. Manter o job aqui geraria mensagem duplicada quando o app
    estivesse acordado na hora.
    """
    return obter_agendador()


# Ativa o agendador
cron = inicializar_agendador_cron()

# Configuração da página
st.set_page_config(
    page_title="Painel WhatsApp ICM",
    page_icon="📌",
    layout="wide",
)

st.title("📌 Painel de Automação do WhatsApp")

st.success(
    "🤖 **Disparo automático diário às 00:00 (Brasília)** para o **ICM** e o "
    "**Zoom**, executado pelo **GitHub Actions** (`.github/workflows/disparo-diario.yml`). "
    "Funciona mesmo com este app hibernado."
)

st.caption(
    "ℹ️ O agendador interno cuida apenas dos **envios avulsos** criados na página "
    "💬 Mensagens. O disparo diário é feito pelo GitHub Actions — o histórico de "
    "cada execução fica na aba *Actions* do repositório."
)

st.markdown(
    """
### Bem-vindo ao Sistema de Gestão e Disparos!

Acesse o menu de navegação na **barra lateral à esquerda** para utilizar as funcionalidades:

* **🎉 Aniversariantes ICM**: consulta da lista do `data.pdf` (com grupos de assistência) e disparo para o grupo do ICM.
* **🎉 Aniversariantes Zoom**: consulta da lista manual `aniversariantes_zoom.csv` (ordenada por mês/dia) e disparo para o grupo do Zoom.
* **💬 Mensagens**: envio de comunicados para grupos e contatos individuais, com opção de **agendar** o disparo para uma data/hora.

---
"""
)

# Validação visual das chaves no painel
apikey = os.getenv("EVOLUTION_APIKEY")
instance = os.getenv("EVOLUTION_INSTANCE")

if apikey and instance:
    st.info(f"✅ Conectado à instância: `{instance}`")
else:
    st.error("❌ Atenção: As credenciais da Evolution API não foram identificadas. Verifique o `.env` ou as *Secrets* do Streamlit Cloud.")

# Status dos destinos configurados
st.markdown("#### 🎯 Destinos dos disparos automáticos")

if JID_GRUPO_IGREJA_FIXO:
    st.info(f"ICM: **{NOME_GRUPO_IGREJA_FIXO}** — `{JID_GRUPO_IGREJA_FIXO}`")
else:
    st.error("ICM: JID não configurado (`JID_GRUPO_IGREJA_FIXO`).")

if JID_GRUPO_ZOOM:
    st.info(f"ZOOM: **{NOME_GRUPO_ZOOM}** — `{JID_GRUPO_ZOOM}`")
else:
    st.warning(
        f"Zoom: **{NOME_GRUPO_ZOOM}** — JID não configurado. "
        "Adicione `JID_GRUPO_ZOOM` no `.env` para ativar o disparo automático "
        "(a página do Zoom continua funcionando para consulta manual)."
    )
