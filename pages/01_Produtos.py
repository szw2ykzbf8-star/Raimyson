import streamlit as st
import pandas as pd
import datetime
from modules.auth import requer_perfil
from modules.google_sheets import ler_df, escrever_df, append_linha

st.set_page_config(page_title="Produtos", page_icon="📦", layout="wide")
usuario = requer_perfil(["admin", "comprador"])

st.title("📦 Cadastro de Produtos")

df = ler_df("produtos")

tab_lista, tab_novo = st.tabs(["Lista de Produtos", "Novo Produto"])

with tab_lista:
    if df.empty:
        st.info("Nenhum produto cadastrado ainda.")
    else:
        filtro = st.text_input("Filtrar por descrição")
        mostrar_inativos = st.checkbox("Mostrar inativos")

        exibir = df.copy()
        if filtro:
            exibir = exibir[exibir["descricao"].str.contains(filtro, case=False, na=False)]
        if not mostrar_inativos:
            exibir = exibir[exibir["ativo"] == True]

        for i, row in exibir.iterrows():
            with st.expander(f"{'✅' if row['ativo'] else '❌'} {row['descricao']} — {row['unidade_medida']}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    nova_desc = st.text_input("Descrição", value=row["descricao"], key=f"desc_{i}")
                    nova_unidade = st.text_input("Unidade de medida", value=row["unidade_medida"], key=f"un_{i}")
                    nova_obs = st.text_input("Observação", value=row.get("observacao", ""), key=f"obs_{i}")
                with col2:
                    ativo = st.checkbox("Ativo", value=bool(row["ativo"]), key=f"ativo_{i}")
                    if st.button("Salvar", key=f"salvar_{i}"):
                        df.at[i, "descricao"] = nova_desc
                        df.at[i, "unidade_medida"] = nova_unidade
                        df.at[i, "observacao"] = nova_obs
                        df.at[i, "ativo"] = ativo
                        escrever_df("produtos", df)
                        st.success("Produto atualizado!")
                        st.cache_resource.clear()
                        st.rerun()

with tab_novo:
    with st.form("novo_produto"):
        descricao = st.text_input("Descrição *")
        unidade_medida = st.selectbox("Unidade de medida *", ["Unidade", "Kg", "Litro", "Pacote", "Caixa", "Fardo", "Outro"])
        observacao = st.text_input("Observação")
        salvar = st.form_submit_button("Cadastrar Produto")

    if salvar:
        if not descricao:
            st.error("Descrição é obrigatória.")
        else:
            novo_id = int(df["id"].max()) + 1 if not df.empty else 1
            append_linha("produtos", [
                novo_id, descricao, unidade_medida, observacao,
                True, datetime.date.today().isoformat()
            ])
            st.success(f"Produto '{descricao}' cadastrado!")
            st.cache_resource.clear()
            st.rerun()
