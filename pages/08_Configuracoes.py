import streamlit as st
import pandas as pd
import datetime
import io
from modules.auth import requer_permissao, hash_senha, validar_senha
from modules.google_sheets import ler_df, escrever_df, append_linha, atualizar_linha

usuario = requer_permissao("configuracoes")

st.title("⚙️ Configurações")


def _bool(v):
    return v is True or str(v).upper() == "TRUE"


def _display_unidade(row):
    fantasia = str(row.get("nome_fantasia", "") or "").strip()
    return fantasia if fantasia else str(row["nome"])


TODOS_LABEL = "✅ Todas as unidades"
UNIDADES_PROTEGIDAS_IDS = {1, 2, 3, 4}  # IDs das unidades base — editáveis, mas não excluíveis

PAGINAS_PERMISSOES = {
    "pedidos":       "📋 Solicitações",
    "cotacoes":      "💰 Cotações",
    "analise":       "📊 Análise de Preços",
    "recebimento":   "📥 Recebimento NF-e",
    "compra_avulsa": "🧾 Compra Avulsa",
    "ordem":         "🛒 Ordem de Compra",
    "produtos":      "📦 Produtos",
    "fornecedores":  "🏭 Fornecedores",
    "relatorios":    "📈 Relatórios",
}
PERFIL_PADRAO_PERM = {
    "admin":     list(PAGINAS_PERMISSOES.keys()),
    "comprador": ["pedidos","cotacoes","analise","ordem","recebimento","compra_avulsa","produtos","fornecedores","relatorios"],
    "digitador": ["pedidos"],
}

def _perm_stored_to_keys(stored, perfil):
    s = str(stored or "").strip()
    if s:
        return [k for k in s.split(",") if k.strip() in PAGINAS_PERMISSOES]
    return list(PERFIL_PADRAO_PERM.get(perfil, ["pedidos"]))

def _perm_keys_to_stored(keys):
    return ",".join(k for k in keys if k in PAGINAS_PERMISSOES)

tab_unidades, tab_unidades_medida, tab_categorias, tab_usuarios, tab_backup = st.tabs([
    "Unidades Hoteleiras", "Un. de Medida", "Categorias", "Usuários", "Backup / Exportar"
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
                            st.cache_data.clear()
                            st.rerun()

            with col_d:
                st.markdown("&nbsp;")
                btn_ativo = "❌ Inativar" if ativo_val else "✅ Ativar"
                if st.button(btn_ativo, key=f"und_toggle_{i}", use_container_width=True):
                    df_unidades.at[i, "ativo"] = str(not ativo_val)
                    escrever_df("unidades", df_unidades)
                    st.cache_data.clear()
                    st.rerun()
                st.markdown("---")
                if st.button("🗑️ Excluir", key=f"und_del_{i}", use_container_width=True):
                    df_unidades = df_unidades.drop(i).reset_index(drop=True)
                    escrever_df("unidades", df_unidades)
                    st.cache_data.clear()
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
                    bairro_n.strip(), cid_n.strip(), est_n.strip(), "True",
                ])
                st.success(f"Unidade '{nome_n}' adicionada!")
                st.session_state["und_form_v"] += 1
                st.cache_data.clear()
                st.rerun()


# ── TAB: UNIDADES DE MEDIDA ──────────────────────────────────────────────────
with tab_unidades_medida:
    st.subheader("Unidades de Medida Base")
    st.caption("Unidades base (IDs 1–4) podem ser editadas, mas não excluídas.")
    df_um = ler_df("unidades_medida")

    if "um_edit_v" not in st.session_state:
        st.session_state["um_edit_v"] = {}

    for i, row in df_um.iterrows():
        ativo_val = _bool(row.get("ativo", True))
        eh_padrao = int(row.get("id", 0)) in UNIDADES_PROTEGIDAS_IDS
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
                        novo_sig = st.text_input("Sigla", value=str(row.get("nome", "")))
                    with c_desc:
                        nova_desc_edit = st.text_input("Nome completo", value=str(row.get("descricao", "") or ""))
                    if st.form_submit_button("💾 Salvar", use_container_width=True):
                        if not novo_sig.strip():
                            st.error("Sigla é obrigatória.")
                        else:
                            df_um.at[i, "nome"] = novo_sig.strip()
                            df_um.at[i, "descricao"] = nova_desc_edit.strip()
                            escrever_df("unidades_medida", df_um)
                            st.session_state["um_edit_v"][str(i)] = ev + 1
                            st.success("Atualizado!")
                            st.cache_data.clear()
                            st.rerun()

            with col_d:
                st.markdown("&nbsp;")
                btn_label = "❌ Inativar" if ativo_val else "✅ Ativar"
                if st.button(btn_label, key=f"um_toggle_{i}", use_container_width=True):
                    df_um.at[i, "ativo"] = str(not ativo_val)
                    escrever_df("unidades_medida", df_um)
                    st.cache_data.clear()
                    st.rerun()
                if not eh_padrao:
                    st.markdown("---")
                    if st.button("🗑️ Excluir", key=f"um_del_{i}", use_container_width=True):
                        df_um = df_um.drop(i).reset_index(drop=True)
                        escrever_df("unidades_medida", df_um)
                        st.cache_data.clear()
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
                append_linha("unidades_medida", [novo_id, nova_sigla.strip(), nova_desc_um.strip(), "True"])
                st.success(f"Unidade '{nova_sigla.strip()}' adicionada!")
                st.session_state["um_form_v"] += 1
                st.cache_data.clear()
                st.rerun()


# ── TAB: CATEGORIAS ─────────────────────────────────────────────────────────
with tab_categorias:
    st.subheader("Categorias de Produtos")
    df_cats = ler_df("categorias")

    def _next_cat_id(df):
        if df.empty or "id" not in df.columns:
            return 1
        try:
            return int(df["id"].apply(lambda v: int(float(v)) if str(v).strip() not in ("", "nan") else 0).max()) + 1
        except Exception:
            return 1

    if not df_cats.empty:
        cats_sorted = df_cats.sort_values("nome", key=lambda x: x.str.lower(), ignore_index=True)
        for _, crow in cats_sorted.iterrows():
            with st.expander(crow["nome"]):
                col_e, col_d = st.columns([3, 1])
                with col_e:
                    novo_nome_cat = st.text_input("Nome", value=crow["nome"], key=f"cat_nome_{crow['id']}")
                    if st.button("💾 Salvar", key=f"cat_salvar_{crow['id']}", use_container_width=True):
                        nome_limpo = novo_nome_cat.strip()
                        if not nome_limpo:
                            st.error("Nome não pode ser vazio.")
                        else:
                            atualizar_linha("categorias", crow["id"], {"nome": nome_limpo})
                            st.success("Categoria atualizada!")
                            st.cache_data.clear()
                            st.rerun()
                with col_d:
                    st.markdown("&nbsp;")
                    if st.button("🗑️ Excluir", key=f"cat_del_{crow['id']}", use_container_width=True):
                        df_cats_novo = df_cats[df_cats["id"].astype(str) != str(crow["id"])]
                        escrever_df("categorias", df_cats_novo)
                        st.success(f"Categoria '{crow['nome']}' excluída.")
                        st.cache_data.clear()
                        st.rerun()

    st.markdown("---")
    st.markdown("**Adicionar nova categoria**")
    if "cat_form_v" not in st.session_state:
        st.session_state["cat_form_v"] = 0

    with st.form(f"nova_categoria_{st.session_state['cat_form_v']}"):
        nome_cat = st.text_input("Nome da categoria *", placeholder="Ex: Laticínios")
        if st.form_submit_button("➕ Adicionar", use_container_width=True):
            nome_limpo = nome_cat.strip()
            if not nome_limpo:
                st.error("Nome é obrigatório.")
            else:
                nomes_existentes = df_cats["nome"].str.strip().str.lower().tolist() if not df_cats.empty else []
                if nome_limpo.lower() in nomes_existentes:
                    st.error(f"Categoria '{nome_limpo}' já existe.")
                else:
                    append_linha("categorias", [_next_cat_id(df_cats), nome_limpo])
                    st.success(f"Categoria '{nome_limpo}' adicionada!")
                    st.session_state["cat_form_v"] += 1
                    st.cache_data.clear()
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
                        perm_atual = _perm_stored_to_keys(row.get("permissoes", ""), row["perfil"])
                        is_admin_perfil = row["perfil"] == "admin"
                        st.markdown("**Páginas do menu** " + ("*(admin tem acesso total)*" if is_admin_perfil else ""))
                        novas_perm = []
                        cols_perm = st.columns(2)
                        for idx_p, (chave, label) in enumerate(PAGINAS_PERMISSOES.items()):
                            with cols_perm[idx_p % 2]:
                                checked = st.checkbox(
                                    label,
                                    value=chave in perm_atual,
                                    key=f"perm_{i}_{chave}",
                                    disabled=is_admin_perfil,
                                )
                                if checked or is_admin_perfil:
                                    novas_perm.append(chave)
                        if st.form_submit_button("💾 Salvar alterações", use_container_width=True):
                            df_usuarios["permissoes"] = df_usuarios["permissoes"].astype(object)
                            df_usuarios.at[i, "nome"] = novo_nome.strip()
                            df_usuarios.at[i, "perfil"] = novo_perfil
                            df_usuarios.at[i, "unidades_acesso"] = display_to_stored(novo_acesso)
                            df_usuarios.at[i, "permissoes"] = "" if novo_perfil == "admin" else _perm_keys_to_stored(novas_perm)
                            escrever_df("usuarios", df_usuarios)
                            st.success("Usuário atualizado!")
                            st.cache_data.clear()
                            st.rerun()

                with col_d:
                    st.markdown("&nbsp;")
                    btn_ativo = "❌ Inativar" if ativo_val else "✅ Ativar"
                    if st.button(btn_ativo, key=f"toggle_{i}", use_container_width=True):
                        df_usuarios.at[i, "ativo"] = str(not ativo_val)
                        escrever_df("usuarios", df_usuarios)
                        st.cache_data.clear()
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
                                df_usuarios.at[i, "trocar_senha"] = "True"
                                escrever_df("usuarios", df_usuarios)
                                st.session_state["reset_v"][str(i)] = rv + 1
                                st.success("Senha redefinida. Usuário deverá trocá-la no próximo login.")
                                st.cache_data.clear()
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
        st.markdown("**Páginas do menu**")
        perm_padrao_novo = PERFIL_PADRAO_PERM.get("digitador", ["pedidos"])
        novas_perm_u = []
        cols_pn = st.columns(2)
        for idx_p, (chave, label) in enumerate(PAGINAS_PERMISSOES.items()):
            with cols_pn[idx_p % 2]:
                if st.checkbox(label, value=chave in perm_padrao_novo, key=f"nperm_{chave}"):
                    novas_perm_u.append(chave)
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
                perm_str = "" if perfil_u == "admin" else _perm_keys_to_stored(novas_perm_u)
                append_linha("usuarios", [
                    novo_id, nome_u.strip(), login_u.strip(),
                    hash_senha(senha_u), perfil_u, acesso_str, "True", "True", perm_str,
                ])
                st.success(f"Usuário '{login_u}' criado! Ele deverá trocar a senha no primeiro login.")
                st.session_state["usr_form_v"] += 1
                st.cache_data.clear()
                st.rerun()


# ── TAB: BACKUP ──────────────────────────────────────────────────────────────
with tab_backup:
    import os as _os
    from config import SHEETS
    from modules.google_sheets import exportar_para_sheets

    _usando_pg = bool(_os.environ.get("DATABASE_URL"))

    if _usando_pg:
        st.success("🐘 **Banco de dados: PostgreSQL (Railway)**")
        st.caption("Google Sheets está disponível apenas como backup.")
    else:
        st.info("📊 **Banco de dados: Google Sheets**")
        st.caption("Configure DATABASE_URL no Railway para migrar para PostgreSQL.")

    # ── Backup PostgreSQL → Google Sheets ────────────────────────────────────
    if _usando_pg:
        st.markdown("---")
        st.markdown("### Backup para Google Sheets")
        st.caption("Exporta todos os dados do PostgreSQL para a planilha Google Sheets.")
        if st.button("☁️ Exportar PostgreSQL → Google Sheets"):
            with st.spinner("Exportando…"):
                resultado = exportar_para_sheets()
            erros = {k: v for k, v in resultado.items() if isinstance(v, str)}
            ok = {k: v for k, v in resultado.items() if not isinstance(v, str)}
            st.success(f"✅ Backup concluído! {len(ok)} tabelas exportadas.")
            if erros:
                st.error("Erros:")
                for k, e in erros.items():
                    st.caption(f"• {k}: {e}")

    # ── Exportar Excel ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Exportar como Excel")
    st.caption("Baixa todos os dados como arquivo .xlsx para guardar localmente.")
    if st.button("Gerar arquivo Excel"):
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

    # ── Importar Excel ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Importar de Excel")
    arquivo = st.file_uploader("Selecione o arquivo Excel de backup", type=["xlsx"])
    if arquivo:
        xls = pd.read_excel(arquivo, sheet_name=None)
        st.write(f"Abas encontradas: {list(xls.keys())}")
        if st.button("Importar (sobrescreve dados atuais)", type="primary"):
            for chave, nome_aba in SHEETS.items():
                if nome_aba in xls:
                    escrever_df(chave, xls[nome_aba])
            st.success("Importação concluída!")
            st.cache_data.clear()
            st.rerun()
