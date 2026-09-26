import streamlit as st
import pandas as pd
import datetime
from modules.auth import requer_permissao
from modules.google_sheets import ler_df, escrever_df, append_linha

usuario = requer_permissao("fornecedores")

st.title("🏭 Cadastro de Fornecedores")


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_ativo(v):
    return v is True or str(v).upper() == "TRUE"


def limpar_cnpj(cnpj: str) -> str:
    return "".join(c for c in cnpj if c.isdigit())


def formatar_cnpj(digits: str) -> str:
    d = limpar_cnpj(digits)
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"
    return digits


def formatar_telefone(raw: str) -> str:
    d = "".join(c for c in (raw or "") if c.isdigit())
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return raw or ""


def consultar_cnpj_api(cnpj_digits: str) -> dict | None:
    try:
        import requests
        resp = requests.get(
            f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_digits}",
            timeout=15,
            headers={"User-Agent": "H-Hoteis-Compras/1.0"},
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def extrair_dados(api: dict) -> dict:
    tipo = api.get("descricao_tipo_de_logradouro", "") or ""
    logr = api.get("logradouro", "") or ""
    logradouro = f"{tipo} {logr}".strip() if tipo else logr
    return {
        "razao_social":  api.get("razao_social",  "") or "",
        "nome_fantasia": api.get("nome_fantasia",  "") or "",
        "cnpj":          formatar_cnpj(api.get("cnpj", "") or ""),
        "telefone":      formatar_telefone(api.get("ddd_telefone_1", "") or ""),
        "cep":           api.get("cep",        "") or "",
        "logradouro":    logradouro,
        "numero":        api.get("numero",     "") or "",
        "complemento":   api.get("complemento","") or "",
        "bairro":        api.get("bairro",     "") or "",
        "cidade":        api.get("municipio",  "") or "",
        "estado":        api.get("uf",         "") or "",
        "situacao":      api.get("descricao_situacao_cadastral", "") or "",
    }


def _aplicar_lookup(prefix: str, dados: dict, campos: list[str]):
    """Copia dados do lookup para os widgets pelo prefixo de chave."""
    for campo in campos:
        sk = f"{prefix}_{campo}"
        if campo in dados:
            st.session_state[sk] = dados[campo]


# Campos preenchidos automaticamente pela API (exceto nome_contato)
_CAMPOS_API = ["razao_social", "nome_fantasia", "cnpj", "telefone",
               "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "estado"]

# ── Load ──────────────────────────────────────────────────────────────────────

df = ler_df("fornecedores")

tab_lista, tab_novo = st.tabs(["Lista de Fornecedores", "Novo Fornecedor"])

# ── Tab: Lista ────────────────────────────────────────────────────────────────

with tab_lista:
    if df.empty:
        st.info("Nenhum fornecedor cadastrado ainda.")
    else:
        col_f, col_i = st.columns([3, 1])
        with col_f:
            filtro = st.text_input("Filtrar por nome ou CNPJ")
        with col_i:
            mostrar_inativos = st.checkbox("Mostrar inativos")

        exibir = df.copy()
        if filtro:
            mask_nome = exibir["razao_social"].str.contains(filtro, case=False, na=False)
            mask_cnpj = exibir["cnpj"].astype(str).str.contains(filtro, case=False, na=False)
            exibir = exibir[mask_nome | mask_cnpj]
        if not mostrar_inativos:
            exibir = exibir[exibir["ativo"].apply(is_ativo)]

        for i, row in exibir.iterrows():
            nf = str(row.get("nome_fantasia", "") or "")
            label_nf = f" / {nf}" if nf else ""
            icone = "✅" if is_ativo(row["ativo"]) else "❌"
            with st.expander(f"{icone} {row['razao_social']}{label_nf}  —  {row.get('cnpj', '')}"):

                # ── Botão de consulta CNPJ (fora de form) ────────────────
                col_cl, col_cbt = st.columns([3, 1])
                with col_cl:
                    st.caption("Consultar CNPJ para atualizar dados da Receita Federal")
                with col_cbt:
                    if st.button("🔍 Consultar CNPJ", key=f"lkp_btn_{i}", use_container_width=True):
                        cnpj_atual = st.session_state.get(f"e_cnpj_{i}", str(row.get("cnpj", "")))
                        digits = limpar_cnpj(cnpj_atual)
                        if len(digits) != 14:
                            st.error("CNPJ inválido.")
                        else:
                            with st.spinner("Consultando…"):
                                api_data = consultar_cnpj_api(digits)
                            if api_data:
                                dados_api = extrair_dados(api_data)
                                _aplicar_lookup(f"e", dados_api, _CAMPOS_API)
                                st.success(f"✅ {dados_api['razao_social']} — {dados_api['situacao']}")
                                st.rerun()
                            else:
                                st.error("CNPJ não encontrado ou serviço indisponível.")

                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    razao   = st.text_input("Razão Social *",  value=str(row.get("razao_social",  "") or ""), key=f"e_razao_social_{i}")
                    nfant   = st.text_input("Nome Fantasia",   value=str(row.get("nome_fantasia", "") or ""), key=f"e_nome_fantasia_{i}")
                    cnpj_e  = st.text_input("CNPJ",           value=str(row.get("cnpj",          "") or ""), key=f"e_cnpj_{i}")
                with col2:
                    contato = st.text_input("Nome do Contato", value=str(row.get("nome_contato",  "") or ""), key=f"e_nome_contato_{i}")
                    tel     = st.text_input("Telefone",        value=str(row.get("telefone",      "") or ""), key=f"e_telefone_{i}")

                st.markdown("**Endereço**")
                col3, col4 = st.columns([3, 1])
                with col3:
                    logr  = st.text_input("Logradouro", value=str(row.get("logradouro", "") or ""), key=f"e_logradouro_{i}")
                with col4:
                    num   = st.text_input("Número",     value=str(row.get("numero",     "") or ""), key=f"e_numero_{i}")
                comp  = st.text_input("Complemento",   value=str(row.get("complemento","") or ""), key=f"e_complemento_{i}")
                col5, col6, col7, col8 = st.columns([2, 2, 2, 1])
                with col5:
                    bairro = st.text_input("Bairro",  value=str(row.get("bairro", "") or ""), key=f"e_bairro_{i}")
                with col6:
                    cidade = st.text_input("Cidade",  value=str(row.get("cidade", "") or ""), key=f"e_cidade_{i}")
                with col7:
                    cep    = st.text_input("CEP",     value=str(row.get("cep",    "") or ""), key=f"e_cep_{i}")
                with col8:
                    estado = st.text_input("UF",      value=str(row.get("estado", "") or ""), key=f"e_estado_{i}", max_chars=2)

                ped_min_val = row.get("pedido_minimo", "")
                try:
                    ped_min_val = float(ped_min_val) if ped_min_val not in ("", None) else 0.0
                except (ValueError, TypeError):
                    ped_min_val = 0.0
                ped_min_e = st.number_input(
                    "Pedido mínimo (R$)",
                    value=ped_min_val,
                    min_value=0.0,
                    step=10.0,
                    format="%.2f",
                    key=f"e_pedido_minimo_{i}",
                    help="Valor mínimo de compra exigido pelo fornecedor",
                )

                col_at, col_sv = st.columns([1, 1])
                with col_at:
                    ativo_e = st.checkbox("Ativo", value=is_ativo(row["ativo"]), key=f"e_ativo_{i}")
                with col_sv:
                    if st.button("💾 Salvar", key=f"salvar_{i}", use_container_width=True):
                        if not st.session_state.get(f"e_razao_social_{i}", "").strip():
                            st.error("Razão Social é obrigatória.")
                        else:
                            df["nome_fantasia"] = df.get("nome_fantasia", pd.Series(dtype=object)).astype(object)
                            for col in ["cep","logradouro","numero","complemento","bairro","cidade","estado","pedido_minimo"]:
                                if col not in df.columns:
                                    df[col] = ""
                                df[col] = df[col].astype(object)
                            df.at[i, "razao_social"]  = st.session_state[f"e_razao_social_{i}"]
                            df.at[i, "nome_fantasia"] = st.session_state[f"e_nome_fantasia_{i}"]
                            df.at[i, "cnpj"]          = st.session_state[f"e_cnpj_{i}"]
                            df.at[i, "nome_contato"]  = st.session_state[f"e_nome_contato_{i}"]
                            df.at[i, "telefone"]      = st.session_state[f"e_telefone_{i}"]
                            df.at[i, "logradouro"]    = st.session_state[f"e_logradouro_{i}"]
                            df.at[i, "numero"]        = st.session_state[f"e_numero_{i}"]
                            df.at[i, "complemento"]   = st.session_state[f"e_complemento_{i}"]
                            df.at[i, "bairro"]        = st.session_state[f"e_bairro_{i}"]
                            df.at[i, "cidade"]        = st.session_state[f"e_cidade_{i}"]
                            df.at[i, "cep"]           = st.session_state[f"e_cep_{i}"]
                            df.at[i, "estado"]        = st.session_state[f"e_estado_{i}"]
                            df.at[i, "pedido_minimo"] = st.session_state[f"e_pedido_minimo_{i}"]
                            df.at[i, "ativo"]         = str(ativo_e)
                            escrever_df("fornecedores", df)
                            st.success("Fornecedor atualizado!")
                            st.cache_data.clear()
                            st.rerun()

# ── Tab: Novo ─────────────────────────────────────────────────────────────────

with tab_novo:
    if "forn_form_v" not in st.session_state:
        st.session_state["forn_form_v"] = 0

    _fv = st.session_state["forn_form_v"]

    st.markdown("#### Consultar CNPJ")
    col_ci, col_cb = st.columns([3, 1])
    with col_ci:
        cnpj_busca = st.text_input(
            "CNPJ",
            placeholder="00.000.000/0000-00 ou apenas os 14 dígitos",
            key=f"novo_cnpj_busca_{_fv}",
        )
    with col_cb:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button("🔍 Consultar", use_container_width=True, key=f"btn_consultar_cnpj_{_fv}"):
            digits = limpar_cnpj(cnpj_busca)
            if len(digits) != 14:
                st.error("CNPJ deve ter 14 dígitos.")
            else:
                with st.spinner("Consultando Receita Federal…"):
                    api_data = consultar_cnpj_api(digits)
                if api_data:
                    dados_api = extrair_dados(api_data)
                    st.session_state["novo_cnpj_dados"] = dados_api
                    if dados_api["situacao"] and dados_api["situacao"].upper() != "ATIVA":
                        st.warning(f"Situação cadastral: **{dados_api['situacao']}**")
                    else:
                        st.success(f"✅ {dados_api['razao_social']} — {dados_api['situacao']}")
                else:
                    st.error("CNPJ não encontrado ou serviço indisponível.")
                    st.session_state.pop("novo_cnpj_dados", None)

    dados = st.session_state.get("novo_cnpj_dados", {})

    st.markdown("---")
    st.markdown("#### Dados do Fornecedor")

    with st.form(f"novo_fornecedor_{_fv}"):
        col1, col2 = st.columns(2)
        with col1:
            razao_social  = st.text_input("Razão Social *",  value=dados.get("razao_social",  ""))
            nome_fantasia = st.text_input("Nome Fantasia",   value=dados.get("nome_fantasia",  ""))
            cnpj_form     = st.text_input("CNPJ *",          value=dados.get("cnpj", formatar_cnpj(limpar_cnpj(cnpj_busca)) if cnpj_busca else ""))
        with col2:
            nome_contato = st.text_input("Nome do Contato *", placeholder="Preenchimento manual")
            telefone     = st.text_input("Telefone/WhatsApp", value=dados.get("telefone", ""))

        st.markdown("**Endereço**")
        col3, col4 = st.columns([3, 1])
        with col3:
            logradouro = st.text_input("Logradouro", value=dados.get("logradouro", ""))
        with col4:
            numero     = st.text_input("Número",     value=dados.get("numero",     ""))
        complemento = st.text_input("Complemento",  value=dados.get("complemento", ""))

        col5, col6, col7, col8 = st.columns([2, 2, 2, 1])
        with col5:
            bairro = st.text_input("Bairro",  value=dados.get("bairro", ""))
        with col6:
            cidade = st.text_input("Cidade",  value=dados.get("cidade", ""))
        with col7:
            cep    = st.text_input("CEP",     value=dados.get("cep",    ""))
        with col8:
            estado = st.text_input("UF",      value=dados.get("estado", ""), max_chars=2)

        pedido_minimo = st.number_input(
            "Pedido mínimo (R$)",
            value=0.0,
            min_value=0.0,
            step=10.0,
            format="%.2f",
            help="Valor mínimo de compra exigido pelo fornecedor (0 = sem mínimo)",
        )

        salvar = st.form_submit_button("✅ Cadastrar Fornecedor", use_container_width=True)

    if salvar:
        if not razao_social.strip() or not cnpj_form.strip() or not nome_contato.strip():
            st.error("Razão Social, CNPJ e Nome do Contato são obrigatórios.")
        else:
            novo_id = int(df["id"].max()) + 1 if not df.empty else 1
            append_linha("fornecedores", [
                novo_id,
                razao_social.strip(),
                cnpj_form.strip(),
                nome_contato.strip(),
                telefone.strip(),
                "True",
                datetime.date.today().isoformat(),
                nome_fantasia.strip(),
                cep.strip(),
                logradouro.strip(),
                numero.strip(),
                complemento.strip(),
                bairro.strip(),
                cidade.strip(),
                estado.strip(),
                pedido_minimo,
            ])
            st.success(f"Fornecedor '{razao_social}' cadastrado!")
            st.session_state["forn_form_v"] += 1
            st.session_state.pop("novo_cnpj_dados", None)
            st.cache_data.clear()
            st.rerun()
