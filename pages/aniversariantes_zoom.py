from datetime import datetime
import sys
from pathlib import Path

import streamlit as st

# Garante que o módulo compartilhado (comum.py, na raiz) seja encontrado
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.comum import (  # noqa: E402
    ARQUIVO_ZOOM,
    JID_GRUPO_ZOOM,
    MESES_MAP,
    NOME_GRUPO_ZOOM,
    enviar_via_evolution_api,
    link_whatsapp,
    montar_mensagem_zoom,
    nomes_sem_genero,
    read_and_parse_csv,
)


def render_pagina() -> None:
    st.set_page_config(page_title="Aniversariantes Zoom", layout="wide")
    st.title("🎉 Aniversariantes Zoom")

    df = read_and_parse_csv(ARQUIVO_ZOOM)

    if df.empty:
        st.error(
            "Lista de aniversariantes do Zoom não encontrada ou inválida. "
            f"Verifique o arquivo: {ARQUIVO_ZOOM}"
        )
        st.caption("Formato esperado: colunas `Nome` e `Data Nasc.` (dd/mm).")
        return

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

    st.sidebar.subheader("🎯 Destino Fixo (Zoom)")
    if JID_GRUPO_ZOOM:
        st.sidebar.info(
            f"**Grupo:** {NOME_GRUPO_ZOOM}\n\n**JID:** `{JID_GRUPO_ZOOM}`"
        )
    else:
        st.sidebar.warning(
            f"**Grupo:** {NOME_GRUPO_ZOOM}\n\n"
            "JID não configurado. Adicione `JID_GRUPO_ZOOM` no `.env` para "
            "liberar o disparo."
        )

    st.subheader("Seleção de Data para Consulta")
    data_selecionada = st.date_input("Escolha a data desejada:", value=datetime.now())
    data_str = data_selecionada.strftime("%d/%m")

    df_hoje = df[df["Data Nasc."] == data_str]

    st.subheader(f"Aniversariantes em {data_str}")

    if not df_hoje.empty:
        st.success(f"Encontrado(s) {len(df_hoje)} aniversariante(s) em {data_str}!")

        mensagem = montar_mensagem_zoom(df_hoje, data_str)
        st.code(mensagem, language="markdown")

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                f"🚀 Disparar para {NOME_GRUPO_ZOOM}",
                width="stretch",
                disabled=not JID_GRUPO_ZOOM,
            ):
                with st.spinner("Enviando via Evolution API..."):
                    sucesso, retorno = enviar_via_evolution_api(
                        mensagem, JID_GRUPO_ZOOM
                    )
                if sucesso:
                    st.success(f"Mensagem enviada para o grupo {NOME_GRUPO_ZOOM}!")
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

    st.sidebar.subheader("Filtros da Lista Zoom")
    meses_disponiveis = [
        MESES_MAP[m] for m in sorted(df["Mês_Num"].unique()) if m in MESES_MAP
    ]
    opcao_mes = st.sidebar.selectbox("Filtrar por Mês:", ["Todos"] + meses_disponiveis)

    df_filtrado = df.copy()
    if opcao_mes != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Mês"] == opcao_mes]

    c1, c2 = st.columns(2)
    c1.metric("Pessoas na Lista", len(df_filtrado))
    c2.metric("Meses com Aniversário", len(df_filtrado["Mês"].unique()))

    st.dataframe(
        df_filtrado[["Número", "Data Nasc.", "Mês", "Dia", "Nome"]],
        width="stretch",
        hide_index=True,
    )


# O Streamlit executa páginas com __name__ == "__main__"
if __name__ == "__main__":
    render_pagina()
