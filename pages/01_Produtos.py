import streamlit as st
import pandas as pd
import datetime
from modules.auth import requer_perfil
from modules.google_sheets import ler_df, escrever_df, append_linha

st.set_page_config(page_title="Produtos", page_icon="📦", layout="wide")
usuario = requer_perfil(["admin", "comprador"])

st.title("📦 Cadastro de Produtos")


def is_ativo(v):
    return v is True or str(v).upper() == "TRUE"


df = ler_df("produtos")

df_um = ler_df("unidades_medida")
if not df_um.empty:
    df_um_ativas = df_um[df_um["ativo"].apply(is_ativo)]
    # "kg (Kilograma)" se tiver descricao, senão só "kg"
    opcoes_unidade_base = [
        f"{r['nome']} ({r['descricao']})" if r.get("descricao") else r["nome"]
        for _, r in df_um_ativas.iterrows()
    ]
    # mapa label → sigla para salvar só a sigla no banco
    mapa_sigla = {
        f"{r['nome']} ({r['descricao']})" if r.get("descricao") else r["nome"]: r["nome"]
        for _, r in df_um_ativas.iterrows()
    }
else:
    opcoes_unidade_base = ["kg", "litro", "unidade"]
    mapa_sigla = {v: v for v in opcoes_unidade_base}

if not opcoes_unidade_base:
    opcoes_unidade_base = ["kg", "litro", "unidade"]
    mapa_sigla = {v: v for v in opcoes_unidade_base}

tab_lista, tab_novo = st.tabs(["Lista de Produtos", "Novo Produto"])

with tab_lista:
    if df.empty:
        st.info("Nenhum produto cadastrado ainda.")
    else:
        col_f, col_i = st.columns([3, 1])
        with col_f:
            filtro = st.text_input("Filtrar por descrição")
        with col_i:
            mostrar_inativos = st.checkbox("Mostrar inativos")

        exibir = df.copy()
        if filtro:
            exibir = exibir[exibir["descricao"].str.contains(filtro, case=False, na=False)]
        if not mostrar_inativos:
            exibir = exibir[exibir["ativo"].apply(is_ativo)]

        for i, row in exibir.iterrows():
            apres = row.get("apresentacao", "")
            ub = row.get("unidade_base", "")
            qtd = row.get("qtd_base_por_apresentacao", "")
            icone = "✅" if is_ativo(row["ativo"]) else "❌"
            label = f"{icone} {row['descricao']}  —  {apres}  (base: {qtd} {ub})"
            with st.expander(label):
                col1, col2 = st.columns([3, 1])
                with col1:
                    nova_desc = st.text_input("Descrição *", value=row["descricao"], key=f"desc_{i}")
                    nova_apres = st.text_input(
                        "Apresentação *", value=str(apres), key=f"apres_{i}",
                        help="Como o produto é vendido. Ex: Pacote 5kg, Fardo c/6 pct"
                    )
                    col_a, col_b = st.columns(2)
                    with col_a:
                        # Produto salva sigla (ex: "kg"); label pode ser "kg (Kilograma)"
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
                            df.at[i, "descricao"] = nova_desc
                            df.at[i, "apresentacao"] = nova_apres
                            df.at[i, "unidade_base"] = nova_ub
                            df.at[i, "qtd_base_por_apresentacao"] = nova_qtd
                            df.at[i, "observacao"] = nova_obs
                            df.at[i, "ativo"] = novo_ativo
                            escrever_df("produtos", df)
                            st.success("Produto atualizado!")
                            st.cache_resource.clear()
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
            ])
            st.success(f"Produto '{descricao}' cadastrado com sucesso!")
            st.session_state["prod_form_v"] += 1
            st.cache_resource.clear()
            st.rerun()
