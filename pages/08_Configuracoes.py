import streamlit as st
import pandas as pd
import datetime
import json
import io
from modules.auth import requer_perfil
from modules.google_sheets import ler_df, escrever_df, append_linha

st.set_page_config(page_title="Configurações", page_icon="⚙️", layout="wide")
usuario = requer_perfil(["admin"])

st.title("⚙️ Configurações")

tab_unidades, tab_usuarios, tab_orcamento, tab_backup = st.tabs([
    "Unidades", "Usuários", "Orçamentos", "Backup / Exportar"
])

with tab_unidades:
    st.subheader("Unidades (CNPJs)")
    df_unidades = ler_df("unidades")

    if not df_unidades.empty:
        st.dataframe(df_unidades, use_container_width=True, hide_index=True)

    with st.form("nova_unidade"):
        nome = st.text_input("Nome da unidade")
        cnpj = st.text_input("CNPJ")
        if st.form_submit_button("Adicionar Unidade"):
            novo_id = int(df_unidades["id"].max()) + 1 if not df_unidades.empty else 1
            append_linha("unidades", [novo_id, nome, cnpj, True])
            st.success(f"Unidade '{nome}' adicionada!")
            st.cache_resource.clear()
            st.rerun()

with tab_usuarios:
    st.subheader("Usuários do Sistema")
    from modules.auth import hash_senha
    df_usuarios = ler_df("usuarios")

    if not df_usuarios.empty:
        exibir = df_usuarios[["id", "nome", "login", "perfil", "unidades_acesso", "ativo"]].copy()
        st.dataframe(exibir, use_container_width=True, hide_index=True)

    df_unidades = ler_df("unidades")
    unidades_nomes = df_unidades["nome"].tolist() if not df_unidades.empty else []

    with st.form("novo_usuario"):
        nome_u = st.text_input("Nome completo")
        login_u = st.text_input("Login")
        senha_u = st.text_input("Senha", type="password")
        perfil_u = st.selectbox("Perfil", ["digitador", "comprador", "admin"])
        acesso_u = st.multiselect("Unidades com acesso", ["todos"] + unidades_nomes)
        if st.form_submit_button("Criar Usuário"):
            if not nome_u or not login_u or not senha_u:
                st.error("Nome, login e senha são obrigatórios.")
            else:
                novo_id = int(df_usuarios["id"].max()) + 1 if not df_usuarios.empty else 1
                acesso_str = "todos" if "todos" in acesso_u else ",".join(acesso_u)
                append_linha("usuarios", [novo_id, nome_u, login_u, hash_senha(senha_u), perfil_u, acesso_str, True])
                st.success(f"Usuário '{login_u}' criado!")
                st.cache_resource.clear()
                st.rerun()

with tab_orcamento:
    st.subheader("Orçamentos Mensais por Unidade")
    df_orcamentos = ler_df("orcamentos")
    df_unidades = ler_df("unidades")

    mes_atual = datetime.date.today().month
    ano_atual = datetime.date.today().year

    col1, col2 = st.columns(2)
    with col1:
        mes_sel = st.selectbox("Mês", range(1, 13), index=mes_atual - 1,
                               format_func=lambda m: ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"][m-1])
    with col2:
        ano_sel = st.number_input("Ano", value=ano_atual, min_value=2020, max_value=2099)

    unidades_nomes = df_unidades["nome"].tolist() if not df_unidades.empty else []
    orc_periodo = df_orcamentos[(df_orcamentos["mes"] == mes_sel) & (df_orcamentos["ano"] == ano_sel)] if not df_orcamentos.empty else pd.DataFrame()

    st.markdown(f"**Orçamentos para {mes_sel:02d}/{ano_sel}**")
    novos_valores = {}
    for unid in unidades_nomes:
        orc_atual = orc_periodo[orc_periodo["unidade"] == unid]
        valor_atual = float(orc_atual.iloc[0]["valor"]) if not orc_atual.empty else 0.0
        novos_valores[unid] = st.number_input(f"{unid}", value=valor_atual, min_value=0.0, step=100.0, format="%.2f")

    if st.button("Salvar Orçamentos"):
        novo_id = int(df_orcamentos["id"].max()) + 1 if not df_orcamentos.empty else 1
        for unid, valor in novos_valores.items():
            existente = df_orcamentos[(df_orcamentos["unidade"] == unid) & (df_orcamentos["mes"] == mes_sel) & (df_orcamentos["ano"] == ano_sel)] if not df_orcamentos.empty else pd.DataFrame()
            if existente.empty:
                append_linha("orcamentos", [novo_id, unid, mes_sel, ano_sel, valor])
                novo_id += 1
            else:
                idx = existente.index[0]
                df_orcamentos.at[idx, "valor"] = valor
                escrever_df("orcamentos", df_orcamentos)
        st.success("Orçamentos salvos!")
        st.cache_resource.clear()
        st.rerun()

with tab_backup:
    st.subheader("Exportar / Importar Banco de Dados")

    from config import SHEETS
    st.markdown("**Exportar todas as abas como Excel**")
    if st.button("Gerar Exportação"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for chave, nome_aba in SHEETS.items():
                try:
                    df = ler_df(chave)
                    df.to_excel(writer, sheet_name=nome_aba[:31], index=False)
                except Exception:
                    pass
        buffer.seek(0)
        st.download_button(
            "⬇️ Baixar backup Excel",
            data=buffer,
            file_name=f"backup_h_hoteis_{datetime.date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.markdown("---")
    st.markdown("**Importar dados de backup**")
    arquivo = st.file_uploader("Selecione o arquivo Excel de backup", type=["xlsx"])
    if arquivo:
        xls = pd.read_excel(arquivo, sheet_name=None)
        abas_encontradas = list(xls.keys())
        st.write(f"Abas encontradas: {abas_encontradas}")
        if st.button("Importar (sobrescreve dados atuais)", type="primary"):
            for chave, nome_aba in SHEETS.items():
                if nome_aba in xls:
                    escrever_df(chave, xls[nome_aba])
            st.success("Importação concluída!")
            st.cache_resource.clear()
            st.rerun()
