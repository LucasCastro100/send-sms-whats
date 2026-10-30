from datetime import datetime
import sys
from pathlib import Path

import streamlit as st

# Garante que o módulo compartilhado (comum.py, na raiz) seja encontrado
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.comum import (  # noqa: E402
    ARQUIVO_PDF,
    JID_GRUPO_IGREJA_FIXO,
    MESES_MAP,
    NOME_GRUPO_IGREJA_FIXO,
    enviar_via_evolution_api,
    link_whatsapp,
    montar_mensagem_aniversariantes,
    nomes_sem_genero,
    read_and_parse_pdf,
)


def render_pagina() -> None:
    st.set_page_config(page_title="Aniversariantes ICM", layout="wide")
    st.title("🎉 Aniversariantes ICM")

    df = read_and_parse_pdf(ARQUIVO_PDF)

    if df.empty:
        st.error(f"Arquivo data.pdf não foi encontrado no caminho: {ARQUIVO_PDF}")
        return

    df["Mês"] = df["Mês_Num"].map(MESES_MAP)

    faltantes = nomes_sem_genero(df)
    if faltantes:
        with st.expander(
            f"⚠️ {len(faltantes)} nome(s) sem gênero cadastrado em generos.json",
            expanded=False,
        ):
            st.caption(
                'Cadastre como `"M"` ou `"F"` no arquivo `generos.json`. '
                "Sem cadastro, a mensagem trata a pessoa como irmão."
            )
            st.write("\n".join(f"- {nome}" for nome in faltantes))

    st.sidebar.subheader("🎯 Destino Fixo (ICM)")
    st.sidebar.info(
        f"**Grupo:** {NOME_GRUPO_IGREJA_FIXO}\n\n**JID:** `{JID_GRUPO_IGREJA_FIXO}`"
    )

    st.subheader("Seleção de Data para Consulta")
    data_selecionada = st.date_input("Escolha a data desejada:", value=datetime.now())
    data_str = data_selecionada.strftime("%d/%m")

    df_hoje = df[df["Data Nasc."] == data_str]

    st.subheader(f"Aniversariantes em {data_str}")

    if not df_hoje.empty:
        st.success(f"Encontrado(s) {len(df_hoje)} aniversariante(s) em {data_str}!")

        mensagem = montar_mensagem_aniversariantes(df_hoje, data_str)
        st.code(mensagem, language="markdown")

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                f"🚀 Disparar para {NOME_GRUPO_IGREJA_FIXO}", width="stretch"
            ):
                with st.spinner("Enviando via Evolution API..."):
                    sucesso, retorno = enviar_via_evolution_api(
                        mensagem, JID_GRUPO_IGREJA_FIXO
                    )
                if sucesso:
                    st.success(f"Mensagem enviada para o grupo {NOME_GRUPO_IGREJA_FIXO}!")
                else:
                    st.error(retorno)

        with col2:
            st.markdown(
                f'<a href="{link_whatsapp(mensagem)}" target="_blank" '
                f'style="text-decoration:none;">'
                f'<button style="background-color:#25D366; color:white; border:none; '
                f'padding:8px 16px; border-radius:5px; font-weight:bold; '
                f'cursor:pointer; width:100%;">Abrir no WhatsApp Web</button></a>',
                unsafe_allow_html=True,
            )
    else:
        st.info(f"Nenhum aniversariante encontrado para a data {data_str}.")

    st.markdown("---")

    # Filtros de navegação da tabela do PDF
    st.sidebar.subheader("Filtros do PDF")
    meses_disponiveis = [
        MESES_MAP[m] for m in sorted(df["Mês_Num"].unique()) if m in MESES_MAP
    ]
    opcao_mes = st.sidebar.selectbox("Filtrar por Mês:", ["Todos"] + meses_disponiveis)

    grupos_disponiveis = sorted(df["Grupo de Assistência"].unique().tolist())
    opcao_grupo = st.sidebar.selectbox(
        "Filtrar por Grupo:", ["Todos"] + grupos_disponiveis
    )

    df_filtrado = df.copy()
    if opcao_mes != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Mês"] == opcao_mes]
    if opcao_grupo != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Grupo de Assistência"] == opcao_grupo]

    c1, c2 = st.columns(2)
    c1.metric("Pessoas Filtradas", len(df_filtrado))
    c2.metric("Grupos Presentes", len(df_filtrado["Grupo de Assistência"].unique()))

    st.dataframe(
        df_filtrado[["Número", "Data Nasc.", "Mês", "Nome", "Grupo de Assistência"]],
        width="stretch",
        hide_index=True,
    )


# O Streamlit executa páginas com __name__ == "__main__"
if __name__ == "__main__":
    render_pagina()
