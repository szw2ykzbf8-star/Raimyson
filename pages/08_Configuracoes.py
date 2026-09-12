import streamlit as st
import pandas as pd
import datetime
import io
from modules.auth import requer_perfil, hash_senha, validar_senha
from modules.google_sheets import ler_df, escrever_df, append_linha

usuario = requer_perfil(["admin"])

st.title("⚙️ Configurações")


def _bool(v):
    return v is True or str(v).upper() == "TRUE"


def _display_unidade(row):
    fantasia = str(row.get("nome_fantasia", "") or "").strip()
    return fantasia if fantasia else str(row["nome"])


TODOS_LABEL = "✅ Todas as unidades"
UNIDADES_PROTEGIDAS = {"kg", "litro", "unidade", "metro"}

tab_unidades, tab_unidades_medida, tab_usuarios, tab_orcamento, tab_backup = st.tabs([
    "Unidades Hoteleiras", "Un. de Medida", "Usuários", "Orçamentos", "Backup / Exportar"
])


# ── TAB: UNIDADES HOTELEIRAS ─────────────────────────────────────────────────
with tab_unidades:
    st.subheader("Unidades Hoteleiras (CNPJs)")
    df_unidades = ler_df("unidades")

    for i, row in df_unidades.iterrows():
        ativo_val = _bool(row.get("ativo", True))
        fantasia = str(row.get("nome_fantasia", "") or "").strip()
        icone = "✅" if ativo_val else "❌"
        label = f"{icone} **{row['nome']}**" + (f" — {fantasia}" if fantasia else "")

        with st.expander(label):
            col_e, col_d = st.columns([3, 1])
            with col_e:
                with st.form(f"edit_und_{i}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        v_nome = st.text_input("Nome interno *", value=str(row.get("nome", "")))
                    with c2:
                        v_fantasia = st.text_input("Nome fantasia", value=fantasia)
                    v_cnpj = st.text_input("CNPJ", value=str(row.get("cnpj", "") or ""), placeholder="00.000.000/0000-00")
                    c_cep, c_log, c_num = st.columns([2, 5, 2])
                    with c_cep:
                        v_cep = st.text_input("CEP", value=str(row.get("cep", "") or ""))
                    with c_log:
                        v_log = st.text_input("Logradouro", value=str(row.get("logradouro", "") or ""))
                    with c_num:
                        v_num = st.text_input("Número", value=str(row.get("numero", "") or ""))
                    c_comp, c_bairro = st.columns(2)
                    with c_comp:
                        v_comp = st.text_input("Complemento", value=str(row.get("complemento", "") or ""))
                    with c_bairro:
                        v_bairro = st.text_input("Bairro", value=str(row.get("bairro", "") or ""))
                    c_cid, c_est = st.columns([4, 2])
                    with c_cid:
                        v_cid = st.text_input("Cidade", value=str(row.get("cidade", "") or ""))
                    with c_est:
                        v_est = st.text_input("Estado (UF)", value=str(row.get("estado", "") or ""), max_chars=2)

                    if st.form_submit_button("💾 Salvar alterações", use_container_width=True):
                        if not v_nome.strip():
                            st.error("Nome é obrigatório.")
                        else:
                            for col, val in [
                                ("nome", v_nome.strip()), ("nome_fantasia", v_fantasia.strip()),
                                ("cnpj", v_cnpj.strip()), ("cep", v_cep.strip()),
                                ("logradouro", v_log.strip()), ("numero", v_num.strip()),
                                ("complemento", v_comp.strip()), ("bairro", v_bairro.strip()),
                                ("cidade", v_cid.strip()), ("estado", v_est.strip()),
                            ]:
                                df_unidades.at[i, col] = val
                            escrever_df("unidades", df_unidades)
                            st.success("Unidade atualizada!")
                            st.cache_resource.clear()
                            st.rerun()

            with col_d:
                st.markdown("&nbsp;")
                btn_ativo = "❌ Inativar" if ativo_val else "✅ Ativar"
                if st.button(btn_ativo, key=f"und_toggle_{i}", use_container_width=True):
                    df_unidades.at[i, "ativo"] = not ativo_val
                    escrever_df("unidades", df_unidades)
                    st.cache_resource.clear()
                    st.rerun()
                st.markdown("---")
                if st.button("🗑️ Excluir", key=f"und_del_{i}", use_container_width=True):
                    df_unidades = df_unidades.drop(i).reset_index(drop=True)
                    escrever_df("unidades", df_unidades)
                    st.cache_resource.clear()
                    st.rerun()

    st.markdown("---")
    st.subheader("Adicionar nova unidade")
    if "und_form_v" not in st.session_state:
        st.session_state["und_form_v"] = 0

    with st.form(f"nova_unidade_{st.session_state['und_form_v']}"):
        c1, c2 = st.columns(2)
        with c1:
            nome_n = st.text_input("Nome interno *", placeholder="Ex: Cancun")
        with c2:
            fantasia_n = st.text_input("Nome fantasia", placeholder="Ex: Hotel Cancun")
        cnpj_n = st.text_input("CNPJ", placeholder="00.000.000/0000-00")
        c_cep, c_log, c_num = st.columns([2, 5, 2])
        with c_cep:
            cep_n = st.text_input("CEP")
        with c_log:
            log_n = st.text_input("Logradouro")
        with c_num:
            num_n = st.text_input("Número")
        c_comp, c_bairro = st.columns(2)
        with c_comp:
            comp_n = st.text_input("Complemento")
        with c_bairro:
            bairro_n = st.text_input("Bairro")
        c_cid, c_est = st.columns([4, 2])
        with c_cid:
            cid_n = st.text_input("Cidade")
        with c_est:
            est_n = st.text_input("Estado (UF)", max_chars=2)

        if st.form_submit_button("➕ Adicionar Unidade", use_container_width=True):
            if not nome_n.strip():
                st.error("Nome é obrigatório.")
            else:
                novo_id = int(df_unidades["id"].max()) + 1 if not df_unidades.empty else 1
                append_linha("unidades", [
                    novo_id, nome_n.strip(), fantasia_n.strip(), cnpj_n.strip(),
                    cep_n.strip(), log_n.strip(), num_n.strip(), comp_n.strip(),
                    bairro_n.strip(), cid_n.strip(), est_n.strip(), True,
                ])
                st.success(f"Unidade '{nome_n}' adicionada!")
                st.session_state["und_form_v"] += 1
                st.cache_resource.clear()
                st.rerun()


# ── TAB: UNIDADES DE MEDIDA ──────────────────────────────────────────────────
with tab_unidades_medida:
    st.subheader("Unidades de Medida Base")
    st.caption("Unidades padrão (kg, litro, unidade, metro) não podem ser excluídas, apenas inativadas.")
    df_um = ler_df("unidades_medida")

    if "um_edit_v" not in st.session_state:
        st.session_state["um_edit_v"] = {}

    for i, row in df_um.iterrows():
        ativo_val = _bool(row.get("ativo", True))
        eh_padrao = str(row.get("nome", "")).lower() in UNIDADES_PROTEGIDAS
        icone = "🔒" if eh_padrao else "📐"
        status_icon = "✅" if ativo_val else "❌"
        desc = str(row.get("descricao", "") or "—")
        label = f"{status_icon} {icone} **{row['nome']}** — {desc}"

        with st.expander(label):
            col_e, col_d = st.columns([3, 1])
            with col_e:
                ev = st.session_state["um_edit_v"].get(str(i), 0)
                with st.form(f"edit_um_{i}_{ev}"):
                    c_sig, c_desc = st.columns([2, 4])
                    with c_sig:
                        novo_sig = st.text_input("Sigla", value=str(row.get("nome", "")), disabled=eh_padrao)
                    with c_desc:
                        nova_desc_edit = st.text_input("Nome completo", value=str(row.get("descricao", "") or ""))
                    if st.form_submit_button("💾 Salvar", use_container_width=True):
                        if not eh_padrao:
                            df_um.at[i, "nome"] = novo_sig.strip()
                        df_um.at[i, "descricao"] = nova_desc_edit.strip()
                        escrever_df("unidades_medida", df_um)
                        st.session_state["um_edit_v"][str(i)] = ev + 1
                        st.success("Atualizado!")
                        st.cache_resource.clear()
                        st.rerun()

            with col_d:
                st.markdown("&nbsp;")
                btn_label = "❌ Inativar" if ativo_val else "✅ Ativar"
                if st.button(btn_label, key=f"um_toggle_{i}", use_container_width=True):
                    df_um.at[i, "ativo"] = not ativo_val
                    escrever_df("unidades_medida", df_um)
                    st.cache_resource.clear()
                    st.rerun()
                if not eh_padrao:
                    st.markdown("---")
                    if st.button("🗑️ Excluir", key=f"um_del_{i}", use_container_width=True):
                        df_um = df_um.drop(i).reset_index(drop=True)
                        escrever_df("unidades_medida", df_um)
                        st.cache_resource.clear()
                        st.rerun()

    st.markdown("---")
    st.markdown("**Adicionar nova unidade de medida**")
    if "um_form_v" not in st.session_state:
        st.session_state["um_form_v"] = 0

    with st.form(f"nova_unidade_medida_{st.session_state['um_form_v']}"):
        c_s, c_d = st.columns([2, 4])
        with c_s:
            nova_sigla = st.text_input("Sigla *", placeholder="Ex: g, mL, dz")
        with c_d:
            nova_desc_um = st.text_input("Nome completo *", placeholder="Ex: Grama, Mililitro, Dúzia")
        if st.form_submit_button("➕ Adicionar", use_container_width=True):
            if not nova_sigla.strip() or not nova_desc_um.strip():
                st.error("Sigla e nome completo são obrigatórios.")
            elif not df_um.empty and nova_sigla.strip().lower() in df_um["nome"].str.lower().tolist():
                st.error(f"A sigla '{nova_sigla}' já existe.")
            else:
                novo_id = int(df_um["id"].max()) + 1 if not df_um.empty else 1
                append_linha("unidades_medida", [novo_id, nova_sigla.strip(), nova_desc_um.strip(), True])
                st.success(f"Unidade '{nova_sigla.strip()}' adicionada!")
                st.session_state["um_form_v"] += 1
                st.cache_resource.clear()
                st.rerun()


# ── TAB: USUÁRIOS ────────────────────────────────────────────────────────────
with tab_usuarios:
    df_usuarios = ler_df("usuarios")
    df_unidades_u = ler_df("unidades")

    if not df_unidades_u.empty:
        mapa_acesso = {_display_unidade(row): row["nome"] for _, row in df_unidades_u.iterrows()}
    else:
        mapa_acesso = {}

    opcoes_acesso = [TODOS_LABEL] + list(mapa_acesso.keys())

    def stored_to_display(stored):
        s = str(stored or "").strip()
        if not s or s == "todos":
            return [TODOS_LABEL]
        nomes = [n.strip() for n in s.split(",") if n.strip()]
        result = [k for k, v in mapa_acesso.items() if v in nomes]
        return result if result else [TODOS_LABEL]

    def display_to_stored(selected):
        if not selected or TODOS_LABEL in selected:
            return "todos"
        nomes = [mapa_acesso[d] for d in selected if d in mapa_acesso]
        return ",".join(nomes) if nomes else "todos"

    if "reset_v" not in st.session_state:
        st.session_state["reset_v"] = {}

    st.subheader("Usuários cadastrados")
    if df_usuarios.empty:
        st.info("Nenhum usuário cadastrado.")
    else:
        for i, row in df_usuarios.iterrows():
            ativo_val = _bool(row.get("ativo", True))
            trocar_val = _bool(row.get("trocar_senha", False))
            icone = "✅" if ativo_val else "❌"
            tags = []
            if trocar_val:
                tags.append("🔄 troca senha no próximo login")
            if not ativo_val:
                tags.append("inativo")
            label = f"{icone} **{row['nome']}** — {row['login']} | {row['perfil']}"
            if tags:
                label += f"  _{', '.join(tags)}_"

            with st.expander(label):
                col_e, col_d = st.columns([3, 1])
                with col_e:
                    with st.form(f"edit_usr_{i}"):
                        novo_nome = st.text_input("Nome completo", value=str(row["nome"]), key=f"en_{i}")
                        novo_perfil = st.selectbox(
                            "Perfil", ["digitador", "comprador", "admin"],
                            index=["digitador", "comprador", "admin"].index(row["perfil"])
                            if row["perfil"] in ["digitador", "comprador", "admin"] else 0,
                            key=f"ep_{i}",
                        )
                        acesso_default = stored_to_display(row.get("unidades_acesso", "todos"))
                        novo_acesso = st.multiselect(
                            "Unidades com acesso",
                            opcoes_acesso,
                            default=[a for a in acesso_default if a in opcoes_acesso],
                            key=f"ea_{i}",
                            help="Selecione 'Todas as unidades' ou uma ou mais unidades específicas.",
                        )
                        if st.form_submit_button("💾 Salvar alterações", use_container_width=True):
                            df_usuarios.at[i, "nome"] = novo_nome.strip()
                            df_usuarios.at[i, "perfil"] = novo_perfil
                            df_usuarios.at[i, "unidades_acesso"] = display_to_stored(novo_acesso)
                            escrever_df("usuarios", df_usuarios)
                            st.success("Usuário atualizado!")
                            st.cache_resource.clear()
                            st.rerun()

                with col_d:
                    st.markdown("&nbsp;")
                    btn_ativo = "❌ Inativar" if ativo_val else "✅ Ativar"
                    if st.button(btn_ativo, key=f"toggle_{i}", use_container_width=True):
                        df_usuarios.at[i, "ativo"] = not ativo_val
                        escrever_df("usuarios", df_usuarios)
                        st.cache_resource.clear()
                        st.rerun()

                    st.markdown("---")
                    st.markdown("**Redefinir senha**")
                    rv = st.session_state["reset_v"].get(str(i), 0)
                    with st.form(f"reset_senha_{i}_{rv}"):
                        nova_s = st.text_input("Nova senha temporária", type="password", key=f"ns_{i}_{rv}")
                        conf_s = st.text_input("Confirmar", type="password", key=f"cs_{i}_{rv}")
                        if st.form_submit_button("🔑 Redefinir", use_container_width=True):
                            erro = validar_senha(nova_s)
                            if erro:
                                st.error(erro)
                            elif nova_s != conf_s:
                                st.error("Senhas não coincidem.")
                            else:
                                df_usuarios.at[i, "senha_hash"] = hash_senha(nova_s)
                                df_usuarios.at[i, "trocar_senha"] = True
                                escrever_df("usuarios", df_usuarios)
                                st.session_state["reset_v"][str(i)] = rv + 1
                                st.success("Senha redefinida. Usuário deverá trocá-la no próximo login.")
                                st.cache_resource.clear()
                                st.rerun()

    st.markdown("---")
    st.subheader("Criar novo usuário")
    st.caption("A senha informada é temporária — o usuário será obrigado a trocá-la no primeiro login.")

    if "usr_form_v" not in st.session_state:
        st.session_state["usr_form_v"] = 0

    with st.form(f"novo_usuario_{st.session_state['usr_form_v']}"):
        col_n1, col_n2 = st.columns(2)
        with col_n1:
            nome_u = st.text_input("Nome completo *")
            login_u = st.text_input("Login *")
        with col_n2:
            senha_u = st.text_input("Senha temporária * (6–72 caracteres)", type="password")
            perfil_u = st.selectbox("Perfil", ["digitador", "comprador", "admin"])
        acesso_u = st.multiselect(
            "Unidades com acesso",
            opcoes_acesso,
            default=[TODOS_LABEL],
            help="Selecione 'Todas as unidades' ou unidades específicas.",
        )
        if st.form_submit_button("➕ Criar Usuário", use_container_width=True):
            erro_s = validar_senha(senha_u) if senha_u else "Senha é obrigatória."
            if not nome_u.strip() or not login_u.strip():
                st.error("Nome e login são obrigatórios.")
            elif erro_s:
                st.error(erro_s)
            elif not df_usuarios.empty and login_u.strip() in df_usuarios["login"].tolist():
                st.error(f"O login '{login_u}' já existe.")
            else:
                novo_id = int(df_usuarios["id"].max()) + 1 if not df_usuarios.empty else 1
                acesso_str = display_to_stored(acesso_u)
                append_linha("usuarios", [
                    novo_id, nome_u.strip(), login_u.strip(),
                    hash_senha(senha_u), perfil_u, acesso_str, True, True,
                ])
                st.success(f"Usuário '{login_u}' criado! Ele deverá trocar a senha no primeiro login.")
                st.session_state["usr_form_v"] += 1
                st.cache_resource.clear()
                st.rerun()


# ── TAB: ORÇAMENTOS ──────────────────────────────────────────────────────────
with tab_orcamento:
    st.subheader("Orçamentos Mensais por Unidade")
    df_orcamentos = ler_df("orcamentos")
    df_unidades = ler_df("unidades")

    mes_atual = datetime.date.today().month
    ano_atual = datetime.date.today().year

    col1, col2 = st.columns(2)
    with col1:
        mes_sel = st.selectbox(
            "Mês", range(1, 13), index=mes_atual - 1,
            format_func=lambda m: ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"][m-1],
        )
    with col2:
        ano_sel = st.number_input("Ano", value=ano_atual, min_value=2020, max_value=2099)

    unidades_nomes = df_unidades["nome"].tolist() if not df_unidades.empty else []
    orc_periodo = (
        df_orcamentos[(df_orcamentos["mes"] == mes_sel) & (df_orcamentos["ano"] == ano_sel)]
        if not df_orcamentos.empty else pd.DataFrame()
    )

    st.markdown(f"**Orçamentos para {mes_sel:02d}/{ano_sel}**")
    novos_valores = {}
    for unid in unidades_nomes:
        orc_atual = orc_periodo[orc_periodo["unidade"] == unid]
        valor_atual = float(orc_atual.iloc[0]["valor"]) if not orc_atual.empty else 0.0
        novos_valores[unid] = st.number_input(f"{unid}", value=valor_atual, min_value=0.0, step=100.0, format="%.2f")

    if st.button("Salvar Orçamentos"):
        novo_id = int(df_orcamentos["id"].max()) + 1 if not df_orcamentos.empty else 1
        for unid, valor in novos_valores.items():
            existente = (
                df_orcamentos[
                    (df_orcamentos["unidade"] == unid) &
                    (df_orcamentos["mes"] == mes_sel) &
                    (df_orcamentos["ano"] == ano_sel)
                ] if not df_orcamentos.empty else pd.DataFrame()
            )
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


# ── TAB: BACKUP ──────────────────────────────────────────────────────────────
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
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.markdown("---")
    st.markdown("**Importar dados de backup**")
    arquivo = st.file_uploader("Selecione o arquivo Excel de backup", type=["xlsx"])
    if arquivo:
        xls = pd.read_excel(arquivo, sheet_name=None)
        st.write(f"Abas encontradas: {list(xls.keys())}")
        if st.button("Importar (sobrescreve dados atuais)", type="primary"):
            for chave, nome_aba in SHEETS.items():
                if nome_aba in xls:
                    escrever_df(chave, xls[nome_aba])
            st.success("Importação concluída!")
            st.cache_resource.clear()
            st.rerun()
