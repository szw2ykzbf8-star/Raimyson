import streamlit as st
import pandas as pd
import datetime
from modules.auth import requer_perfil
from modules.google_sheets import ler_df, escrever_df, append_linha

st.set_page_config(page_title="Fornecedores", page_icon="🏭", layout="wide")
usuario = requer_perfil(["admin", "comprador"])

st.title("🏭 Cadastro de Fornecedores")

df = ler_df("fornecedores")

tab_lista, tab_novo = st.tabs(["Lista de Fornecedores", "Novo Fornecedor"])

with tab_lista:
    if df.empty:
        st.info("Nenhum fornecedor cadastrado ainda.")
    else:
        filtro = st.text_input("Filtrar por nome")
        mostrar_inativos = st.checkbox("Mostrar inativos")

        exibir = df.copy()
        if filtro:
            exibir = exibir[exibir["razao_social"].str.contains(filtro, case=False, na=False)]
        if not mostrar_inativos:
            exibir = exibir[exibir["ativo"] == True]

        for i, row in exibir.iterrows():
            with st.expander(f"{'✅' if row['ativo'] else '❌'} {row['razao_social']}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    razao = st.text_input("Razão Social", value=row["razao_social"], key=f"rs_{i}")
                    cnpj = st.text_input("CNPJ", value=row.get("cnpj", ""), key=f"cnpj_{i}")
                    contato = st.text_input("Nome do Contato", value=row.get("nome_contato", ""), key=f"ct_{i}")
                    telefone = st.text_input("Telefone/WhatsApp", value=row.get("telefone", ""), key=f"tel_{i}")
                with col2:
                    ativo = st.checkbox("Ativo", value=bool(row["ativo"]), key=f"ativo_{i}")
                    if st.button("Salvar", key=f"salvar_{i}"):
                        df.at[i, "razao_social"] = razao
                        df.at[i, "cnpj"] = cnpj
                        df.at[i, "nome_contato"] = contato
                        df.at[i, "telefone"] = telefone
                        df.at[i, "ativo"] = ativo
                        escrever_df("fornecedores", df)
                        st.success("Fornecedor atualizado!")
                        st.cache_resource.clear()
                        st.rerun()

with tab_novo:
    with st.form("novo_fornecedor"):
        razao_social = st.text_input("Razão Social *")
        cnpj = st.text_input("CNPJ *")
        nome_contato = st.text_input("Nome do Contato *")
        telefone = st.text_input("Telefone/WhatsApp *")
        salvar = st.form_submit_button("Cadastrar Fornecedor")

    if salvar:
        if not razao_social or not cnpj or not nome_contato or not telefone:
            st.error("Todos os campos marcados com * são obrigatórios.")
        else:
            novo_id = int(df["id"].max()) + 1 if not df.empty else 1
            append_linha("fornecedores", [
                novo_id, razao_social, cnpj, nome_contato, telefone,
                True, datetime.date.today().isoformat()
            ])
            st.success(f"Fornecedor '{razao_social}' cadastrado!")
            st.cache_resource.clear()
            st.rerun()
