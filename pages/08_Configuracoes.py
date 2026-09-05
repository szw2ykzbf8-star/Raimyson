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

tab_unidades, tab_unidades_medida, tab_usuarios, tab_orcamento, tab_backup = st.tabs([
    "Unidades Hoteleiras", "Un. de Medida", "Usuários", "Orçamentos", "Backup / Exportar"
])

with tab_unidades:
    st.subheader("Unidades Hoteleiras (CNPJs)")
    df_unidades = ler_df("unidades")

    if not df_unidades.empty:
        st.dataframe(df_unidades, use_container_width=True, hide_index=True)

    if "und_form_v" not in st.session_state:
        st.session_state["und_form_v"] = 0

    with st.form(f"nova_unidade_{st.session_state['und_form_v']}"):
        nome = st.text_input("Nome da unidade *", placeholder="Ex: Cancun")
        cnpj = st.text_input("CNPJ", placeholder="00.000.000/0000-00")
        if st.form_submit_button("Adicionar Unidade", use_container_width=True):
            if not nome.strip():
                st.error("Nome é obrigatório.")
            else:
                novo_id = int(df_unidades["id"].max()) + 1 if not df_unidades.empty else 1
                append_linha("unidades", [novo_id, nome.strip(), cnpj.strip(), True])
                st.success(f"Unidade '{nome}' adicionada!")
                st.session_state["und_form_v"] += 1
                st.cache_resource.clear()
                st.rerun()

with tab_unidades_medida:
    st.subheader("Unidades de Medida Base")
    st.caption(
        "Estas unidades são usadas para normalizar e comparar preços entre fornecedores. "
        "Unidades padrão (kg, litro, unidade, metro) não podem ser excluídas, apenas inativadas."
    )

    UNIDADES_PROTEGIDAS = {"kg", "litro", "unidade", "metro"}

    df_um = ler_df("unidades_medida")

    if not df_um.empty:
        col_h1, col_h2, col_h3, col_h4 = st.columns([2, 4, 2, 2])
        col_h1.markdown("**Sigla**")
        col_h2.markdown("**Nome completo**")
        col_h3.markdown("**Status**")
        st.markdown("---")
        for i, row in df_um.iterrows():
            ativo_val = row["ativo"] is True or str(row["ativo"]).upper() == "TRUE"
            eh_padrao = str(row["nome"]).lower() in UNIDADES_PROTEGIDAS
            col1, col2, col3, col4 = st.columns([2, 4, 2, 2])
            with col1:
                st.write(f"**{row['nome']}**" + (" 🔒" if eh_padrao else ""))
            with col2:
                st.write(row.get("descricao", "") or "—")
            with col3:
                st.write("✅ Ativa" if ativo_val else "❌ Inativa")
            with col4:
                btn_label = "Inativar" if ativo_val else "Ativar"
                if st.button(btn_label, key=f"um_toggle_{i}", use_container_width=True):
                    df_um.at[i, "ativo"] = not ativo_val
                    escrever_df("unidades_medida", df_um)
                    st.cache_resource.clear()
                    st.rerun()

    st.markdown("---")
    st.markdown("**Adicionar nova unidade de medida**")

    if "um_form_v" not in st.session_state:
        st.session_state["um_form_v"] = 0

    with st.form(f"nova_unidade_medida_{st.session_state['um_form_v']}"):
        col_s, col_d = st.columns([2, 4])
        with col_s:
            nova_sigla = st.text_input("Sigla *", placeholder="Ex: g, mL, dz")
        with col_d:
            nova_desc_um = st.text_input("Nome completo *", placeholder="Ex: Grama, Mililitro, Dúzia")
        if st.form_submit_button("Adicionar", use_container_width=True):
            if not nova_sigla.strip() or not nova_desc_um.strip():
                st.error("Sigla e nome completo são obrigatórios.")
            elif not df_um.empty and nova_sigla.strip().lower() in df_um["nome"].str.lower().tolist():
                st.error(f"A sigla '{nova_sigla}' já existe.")
            else:
                novo_id = int(df_um["id"].max()) + 1 if not df_um.empty else 1
                append_linha("unidades_medida", [novo_id, nova_sigla.strip(), nova_desc_um.strip(), True])
                st.success(f"Unidade '{nova_sigla.strip()} ({nova_desc_um.strip()})' adicionada!")
                st.session_state["um_form_v"] += 1
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

    if "usr_form_v" not in st.session_state:
        st.session_state["usr_form_v"] = 0

    with st.form(f"novo_usuario_{st.session_state['usr_form_v']}"):
        nome_u = st.text_input("Nome completo *")
        login_u = st.text_input("Login *")
        senha_u = st.text_input("Senha *", type="password")
        perfil_u = st.selectbox("Perfil", ["digitador", "comprador", "admin"])
        acesso_u = st.multiselect("Unidades com acesso", ["todos"] + unidades_nomes)
        if st.form_submit_button("Criar Usuário", use_container_width=True):
            if not nome_u or not login_u or not senha_u:
                st.error("Nome, login e senha são obrigatórios.")
            else:
                novo_id = int(df_usuarios["id"].max()) + 1 if not df_usuarios.empty else 1
                acesso_str = "todos" if "todos" in acesso_u else ",".join(acesso_u)
                append_linha("usuarios", [novo_id, nome_u, login_u, hash_senha(senha_u), perfil_u, acesso_str, True])
                st.success(f"Usuário '{login_u}' criado!")
                st.session_state["usr_form_v"] += 1
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
