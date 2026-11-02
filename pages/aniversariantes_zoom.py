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
    atualizar_exclusoes,
    carregar_exclusoes,
    enviar_via_evolution_api,
    esta_excluido,
    link_whatsapp,
    montar_mensagem_zoom,
    nomes_excluidos,
    nomes_sem_genero,
    read_and_parse_csv,
    remover_excluidos,
)

FONTE = "zoom"


def render_pagina() -> None:
    st.set_page_config(page_title="Aniversariantes Zoom", layout="wide")
    st.title("🎉 Aniversariantes Zoom")

    if st.session_state.pop("exclusoes_zoom_salvas", None):
        st.success("✅ Lista de quem não deve ser citado salva em `data/exclusoes.json`.")

    df = read_and_parse_csv(ARQUIVO_ZOOM)

    if df.empty:
        st.error(
            "Lista de aniversariantes do Zoom não encontrada ou inválida. "
            f"Verifique o arquivo: {ARQUIVO_ZOOM}"
        )
        st.caption("Formato esperado: colunas `Nome` e `Data Nasc.` (dd/mm).")
        return

    faltantes = nomes_sem_genero(df, FONTE)
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
    excluidos_hoje = [n for n in df_hoje["Nome"] if esta_excluido(n, FONTE)]
    df_envio = remover_excluidos(df_hoje, FONTE)

    st.subheader(f"Aniversariantes em {data_str}")

    if not df_hoje.empty and df_envio.empty:
        st.warning(
            "Todos os aniversariantes desta data estão marcados para **não receber** "
            f"em `data/exclusoes.json`: {', '.join(excluidos_hoje)}."
        )
    elif not df_envio.empty:
        st.success(f"Encontrado(s) {len(df_envio)} aniversariante(s) em {data_str}!")

        if excluidos_hoje:
            st.info(
                "🚫 Não serão citados (marcados para não receber): "
                + ", ".join(excluidos_hoje)
            )

        mensagem = montar_mensagem_zoom(df_envio, data_str, fonte=FONTE)
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
    elif df_hoje.empty:
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

    st.markdown("---")

    # ------------------------------------------------------------------
    # Quem não deve ser citado nas mensagens
    # ------------------------------------------------------------------
    st.subheader("🚫 Quem NÃO deve ser citado nas mensagens")
    st.caption(
        "Marque na coluna **Não citar** as pessoas que não devem aparecer no texto "
        "de aniversário e clique em **Salvar**. Vale para o botão **Disparar** "
        "desta tela e para o envio automático das 00:00 (GitHub Actions). "
        "As marcações vão para `data/exclusoes.json` → chave `zoom`."
    )

    tabela_exclusao = df_filtrado[["Nome", "Data Nasc."]].copy()
    tabela_exclusao.insert(
        0,
        "Não citar",
        tabela_exclusao["Nome"].map(lambda nome: esta_excluido(nome, FONTE)),
    )

    editado = st.data_editor(
        tabela_exclusao,
        hide_index=True,
        width="stretch",
        key=f"editor_exclusoes_zoom_{opcao_mes}",
        disabled=["Nome", "Data Nasc."],
        column_config={
            "Não citar": st.column_config.CheckboxColumn(
                "Não citar",
                help="Marque para não citar esta pessoa na mensagem.",
                default=False,
            )
        },
    )

    bloqueados = editado.loc[editado["Não citar"], "Nome"].tolist()
    st.caption(
        f"✔️ Marcados para **não citar** neste filtro: {len(bloqueados)} · "
        f"Total salvo em `exclusoes.json` → `zoom`: {len(nomes_excluidos(FONTE))}"
    )

    with st.expander("Ver conteúdo de `data/exclusoes.json`"):
        st.json(carregar_exclusoes())

    if st.button("💾 Salvar quem não deve ser citado (Zoom)", width="stretch"):
        atualizar_exclusoes(FONTE, df_filtrado["Nome"].tolist(), bloqueados)
        st.session_state["exclusoes_zoom_salvas"] = True
        st.rerun()


# O Streamlit executa páginas com __name__ == "__main__"
if __name__ == "__main__":
    render_pagina()
