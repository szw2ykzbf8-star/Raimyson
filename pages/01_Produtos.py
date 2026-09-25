import streamlit as st
import pandas as pd
import datetime
import io
from modules.auth import requer_permissao
from modules.google_sheets import ler_df, escrever_df, append_linha

usuario = requer_permissao("produtos")

st.title("📦 Cadastro de Produtos")


def is_ativo(v):
    return v is True or str(v).upper() == "TRUE"


df = ler_df("produtos")

df_um = ler_df("unidades_medida")
if not df_um.empty:
    df_um_ativas = df_um[df_um["ativo"].apply(is_ativo)]
    opcoes_unidade_base = [
        f"{r['nome']} ({r['descricao']})" if r.get("descricao") else r["nome"]
        for _, r in df_um_ativas.iterrows()
    ]
    mapa_sigla = {
        f"{r['nome']} ({r['descricao']})" if r.get("descricao") else r["nome"]: r["nome"]
        for _, r in df_um_ativas.iterrows()
    }
else:
    opcoes_unidade_base = ["kg", "lt", "un", "mt"]
    mapa_sigla = {v: v for v in opcoes_unidade_base}

if not opcoes_unidade_base:
    opcoes_unidade_base = ["kg", "lt", "un", "mt"]
    mapa_sigla = {v: v for v in opcoes_unidade_base}

tab_lista, tab_novo, tab_import = st.tabs(["Lista de Produtos", "Novo Produto", "Importar Excel"])

with tab_lista:
    if df.empty:
        st.info("Nenhum produto cadastrado ainda.")
    else:
        col_f, col_i = st.columns([3, 1])
        with col_f:
            filtro = st.text_input("Filtrar por descrição ou código")
        with col_i:
            mostrar_inativos = st.checkbox("Mostrar inativos")

        exibir = df.copy()
        if filtro:
            mask_desc = exibir["descricao"].str.contains(filtro, case=False, na=False)
            mask_cod  = exibir["codigo"].astype(str).str.contains(filtro, case=False, na=False) if "codigo" in exibir.columns else False
            exibir = exibir[mask_desc | mask_cod]
        if not mostrar_inativos:
            exibir = exibir[exibir["ativo"].apply(is_ativo)]

        for i, row in exibir.iterrows():
            apres  = row.get("apresentacao", "")
            ub     = row.get("unidade_base", "")
            qtd    = row.get("qtd_base_por_apresentacao", "")
            cod    = row.get("codigo", "")
            icone  = "✅" if is_ativo(row["ativo"]) else "❌"
            cod_str = f"[{cod}] " if cod and str(cod).strip() else ""
            label  = f"{icone} {cod_str}{row['descricao']}  —  {apres}  (base: {qtd} {ub})"
            with st.expander(label):
                col1, col2 = st.columns([3, 1])
                with col1:
                    novo_cod = st.text_input(
                        "Código", value=str(cod) if cod and str(cod).strip() else "",
                        key=f"cod_{i}",
                        help="Código interno do produto (usado para importar pedidos via estoque mínimo)"
                    )
                    nova_desc = st.text_input("Descrição *", value=row["descricao"], key=f"desc_{i}")
                    nova_apres = st.text_input(
                        "Apresentação *", value=str(apres), key=f"apres_{i}",
                        help="Como o produto é vendido. Ex: Pacote 5kg, Fardo c/6 pct"
                    )
                    col_a, col_b = st.columns(2)
                    with col_a:
                        label_atual = next((k for k, v in mapa_sigla.items() if v == ub), ub)
                        idx_default = opcoes_unidade_base.index(label_atual) if label_atual in opcoes_unidade_base else 0
                        label_ub_edit = st.selectbox(
                            "Unidade base (comparação) *", opcoes_unidade_base,
                            index=idx_default, key=f"ub_{i}",
                            help="Unidade usada para normalizar e comparar preços"
                        )
                        nova_ub = mapa_sigla.get(label_ub_edit, label_ub_edit)
                    with col_b:
                        nova_qtd = st.number_input(
                            "Qtd base por apresentação *",
                            value=float(qtd) if qtd else 1.0,
                            min_value=0.001, step=0.5, key=f"qtd_{i}",
                            help="Qtd da unidade base contida na apresentação. Ex: Pacote 5kg → 5; Fardo c/6 pct de 5kg → 30"
                        )
                    nova_obs = st.text_input("Observação", value=row.get("observacao", ""), key=f"obs_{i}")
                with col2:
                    st.markdown("&nbsp;", unsafe_allow_html=True)
                    novo_ativo = st.checkbox("Ativo", value=is_ativo(row["ativo"]), key=f"ativo_{i}")
                    if st.button("💾 Salvar", key=f"salvar_{i}", use_container_width=True):
                        if not nova_desc or not nova_apres:
                            st.error("Descrição e apresentação são obrigatórias.")
                        else:
                            df["codigo"] = df["codigo"].astype(object) if "codigo" in df.columns else ""
                            df.at[i, "codigo"]      = novo_cod.strip()
                            df.at[i, "descricao"]   = nova_desc
                            df.at[i, "apresentacao"] = nova_apres
                            df.at[i, "unidade_base"] = nova_ub
                            df.at[i, "qtd_base_por_apresentacao"] = nova_qtd
                            df.at[i, "observacao"]  = nova_obs
                            df.at[i, "ativo"]       = novo_ativo
                            escrever_df("produtos", df)
                            st.success("Produto atualizado!")
                            st.cache_data.clear()
                            st.rerun()

with tab_novo:
    st.markdown("#### Cadastrar novo produto")
    st.caption(
        "Separe o **nome** da **embalagem**: descrição é só o produto (ex: *Arroz*), "
        "apresentação é como ele é vendido (ex: *Pacote 5kg*)."
    )

    if "prod_form_v" not in st.session_state:
        st.session_state["prod_form_v"] = 0

    with st.form(f"novo_produto_{st.session_state['prod_form_v']}"):
        codigo = st.text_input(
            "Código",
            placeholder="Ex: 001, AROZ-5KG, 1023",
            help="Código interno do produto. Usado para importar pedidos via relatório de estoque mínimo."
        )
        descricao = st.text_input(
            "Descrição *",
            placeholder="Ex: Arroz, Papel toalha, Detergente",
            help="Nome do produto sem incluir embalagem ou quantidade"
        )
        apresentacao = st.text_input(
            "Apresentação *",
            placeholder="Ex: Pacote 5kg, Fardo c/6 pct, Caixa 12un",
            help="Como o produto é normalmente vendido pelo fornecedor"
        )
        col1, col2 = st.columns(2)
        with col1:
            label_ub = st.selectbox(
                "Unidade base (comparação de preço) *",
                opcoes_unidade_base,
                help="Unidade usada para normalizar e comparar preços entre fornecedores"
            )
            unidade_base = mapa_sigla.get(label_ub, label_ub)
        with col2:
            qtd_base = st.number_input(
                "Qtd da unidade base por apresentação *",
                min_value=0.001, value=1.0, step=0.5,
                help=(
                    "Quantas unidades-base cabem na apresentação:\n"
                    "• Pacote 5kg → 5\n"
                    "• Fardo c/6 pct de 5kg → 30\n"
                    "• Caixa 12un → 12"
                )
            )
        observacao = st.text_input(
            "Observação",
            placeholder="Ex: Perecível. Preferir marca X.",
            help="Informação extra visível apenas internamente"
        )
        salvar = st.form_submit_button("✅ Cadastrar Produto", use_container_width=True)

    if salvar:
        if not descricao.strip() or not apresentacao.strip():
            st.error("Descrição e apresentação são obrigatórias.")
        else:
            novo_id = int(df["id"].max()) + 1 if not df.empty else 1
            append_linha("produtos", [
                novo_id,
                descricao.strip(),
                apresentacao.strip(),
                unidade_base,
                qtd_base,
                observacao.strip(),
                True,
                datetime.date.today().isoformat(),
                codigo.strip(),
            ])
            st.success(f"Produto '{descricao}' cadastrado com sucesso!")
            st.session_state["prod_form_v"] += 1
            st.cache_data.clear()
            st.rerun()

with tab_import:
    st.markdown("#### Importar produtos via Excel")

    # ── Modelo para download ──────────────────────────────────────────────
    _siglas_disponiveis = list(mapa_sigla.values()) or ["kg", "lt", "un", "mt"]
    _modelo = pd.DataFrame([
        {
            "codigo":                     "001",
            "descricao":                  "Arroz",
            "apresentacao":               "Pacote 5kg",
            "unidade_base":               "kg",
            "qtd_base_por_apresentacao":  5,
            "observacao":                 "",
        },
        {
            "codigo":                     "002",
            "descricao":                  "Detergente",
            "apresentacao":               "Frasco 500ml",
            "unidade_base":               "lt",
            "qtd_base_por_apresentacao":  0.5,
            "observacao":                 "Neutro",
        },
    ])
    _buf_modelo = io.BytesIO()
    with pd.ExcelWriter(_buf_modelo, engine="openpyxl") as _w:
        _modelo.to_excel(_w, index=False, sheet_name="Produtos")
    st.download_button(
        "⬇️ Baixar modelo Excel",
        data=_buf_modelo.getvalue(),
        file_name="modelo_produtos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.caption(
        f"Unidades válidas para `unidade_base`: **{', '.join(_siglas_disponiveis)}**  "
        "— use exatamente a sigla cadastrada. O campo `codigo` é opcional."
    )

    # ── Upload ────────────────────────────────────────────────────────────
    arquivo = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type=["xlsx"])

    if arquivo:
        try:
            df_imp = pd.read_excel(arquivo, dtype=str)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            st.stop()

        df_imp.columns = [c.strip().lower().replace(" ", "_") for c in df_imp.columns]

        COLUNAS_OBRIG = ["descricao", "apresentacao", "unidade_base", "qtd_base_por_apresentacao"]
        faltando = [c for c in COLUNAS_OBRIG if c not in df_imp.columns]
        if faltando:
            st.error(f"Colunas obrigatórias não encontradas: **{', '.join(faltando)}**")
            st.info("Baixe o modelo acima e confira os nomes das colunas.")
            st.stop()

        if "observacao" not in df_imp.columns:
            df_imp["observacao"] = ""
        if "codigo" not in df_imp.columns:
            df_imp["codigo"] = ""

        # Normaliza
        df_imp = df_imp.dropna(subset=["descricao"]).copy()
        df_imp["codigo"]      = df_imp["codigo"].fillna("").str.strip()
        df_imp["descricao"]   = df_imp["descricao"].str.strip()
        df_imp["apresentacao"] = df_imp["apresentacao"].fillna("").str.strip()
        df_imp["unidade_base"] = df_imp["unidade_base"].fillna("").str.strip()
        df_imp["observacao"]  = df_imp["observacao"].fillna("").str.strip()
        df_imp["qtd_base_por_apresentacao"] = pd.to_numeric(
            df_imp["qtd_base_por_apresentacao"], errors="coerce"
        )

        # Validação por linha
        desc_existentes = set(df["descricao"].str.strip().str.lower()) if not df.empty else set()
        erros, avisos, ok = [], [], []

        for idx, row in df_imp.iterrows():
            linha = idx + 2
            if not row["descricao"]:
                erros.append(f"Linha {linha}: descrição vazia.")
                continue
            if not row["apresentacao"]:
                erros.append(f"Linha {linha} ({row['descricao']}): apresentação vazia.")
                continue
            if row["unidade_base"] not in _siglas_disponiveis:
                erros.append(
                    f"Linha {linha} ({row['descricao']}): unidade_base "
                    f"'{row['unidade_base']}' inválida. Use: {', '.join(_siglas_disponiveis)}."
                )
                continue
            if pd.isna(row["qtd_base_por_apresentacao"]) or row["qtd_base_por_apresentacao"] <= 0:
                erros.append(
                    f"Linha {linha} ({row['descricao']}): qtd_base_por_apresentacao inválida."
                )
                continue
            if row["descricao"].lower() in desc_existentes:
                avisos.append(f"Linha {linha} ({row['descricao']}): já existe — será ignorada.")
            else:
                ok.append(idx)

        st.markdown(f"**Resumo:** {len(ok)} para importar | {len(avisos)} duplicatas (ignoradas) | {len(erros)} erros")

        if erros:
            with st.expander(f"❌ {len(erros)} erro(s) — corrija no arquivo antes de importar"):
                for e in erros:
                    st.write(e)

        if avisos:
            with st.expander(f"⚠️ {len(avisos)} duplicata(s) que serão ignoradas"):
                for a in avisos:
                    st.write(a)

        if ok:
            st.dataframe(
                df_imp.loc[ok, ["codigo", "descricao", "apresentacao", "unidade_base",
                                "qtd_base_por_apresentacao", "observacao"]],
                use_container_width=True,
                hide_index=True,
            )
            if st.button(f"✅ Importar {len(ok)} produto(s)", use_container_width=True):
                proximo_id = int(df["id"].max()) + 1 if not df.empty else 1
                hoje = datetime.date.today().isoformat()
                novas_linhas = []
                for idx in ok:
                    r = df_imp.loc[idx]
                    novas_linhas.append([
                        proximo_id,
                        r["descricao"],
                        r["apresentacao"],
                        r["unidade_base"],
                        float(r["qtd_base_por_apresentacao"]),
                        r["observacao"],
                        True,
                        hoje,
                        r["codigo"],
                    ])
                    proximo_id += 1

                from modules.google_sheets import get_sheet as _get_sheet
                ws = _get_sheet("produtos")
                ws.append_rows(novas_linhas)
                st.success(f"{len(novas_linhas)} produto(s) importado(s) com sucesso!")
                st.cache_data.clear()
                st.rerun()
        elif not erros:
            st.info("Nenhum produto novo para importar (todos já existem).")
