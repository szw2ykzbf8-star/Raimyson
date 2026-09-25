import streamlit as st
import pandas as pd
import datetime
from modules.auth import requer_permissao
from modules.google_sheets import ler_df, escrever_df, append_linha

usuario = requer_permissao("pedidos")

st.title("📋 Solicitações de Compra")

df_produtos = ler_df("produtos")
df_pedidos  = ler_df("pedidos")
df_itens    = ler_df("itens_pedido")

perfil = usuario["perfil"]
unidades_acesso = usuario["unidades_acesso"]
if unidades_acesso == "todos":
    unidades_disponiveis = ler_df("unidades")["nome"].tolist()
else:
    unidades_disponiveis = [u.strip() for u in str(unidades_acesso).split(",")]


def _safe_int(v):
    try:
        return int(float(v)) if str(v).strip() not in ("", "nan") else 0
    except Exception:
        return 0


def _next_id(df, col="id"):
    if df.empty or col not in df.columns:
        return 1
    try:
        return int(df[col].apply(_safe_int).max()) + 1
    except Exception:
        return 1


# Versão do formulário — incrementada após cada envio para forçar reset dos campos
if "pedido_form_v" not in st.session_state:
    st.session_state["pedido_form_v"] = 0

tab_novo, tab_abertos = st.tabs(["Nova Solicitação", "Solicitações Abertas"])

with tab_novo:
    unidade = st.selectbox("Unidade", unidades_disponiveis)

    produtos_ativos = df_produtos[df_produtos["ativo"] == True] if not df_produtos.empty else pd.DataFrame()

    if produtos_ativos.empty:
        st.warning("Nenhum produto ativo cadastrado.")
    else:
        st.markdown("Preencha a quantidade desejada. Deixe em branco os produtos que não precisa.")
        fv = st.session_state["pedido_form_v"]
        itens_pedido = {}
        for _, prod in produtos_ativos.iterrows():
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**{prod['descricao']}** — {prod['unidade_base']}")
                if prod.get("observacao"):
                    st.caption(prod["observacao"])
            with col2:
                qtd = st.number_input(
                    "Qtd",
                    min_value=0.0, step=0.5,
                    key=f"qtd_{prod['id']}_{fv}",
                    label_visibility="collapsed",
                )
                if qtd > 0:
                    itens_pedido[prod["id"]] = qtd

        if st.button("Enviar Solicitação", type="primary"):
            if not itens_pedido:
                st.error("Selecione ao menos um produto com quantidade.")
            else:
                try:
                    novo_id  = _next_id(df_pedidos)
                    item_id  = _next_id(df_itens)
                    append_linha("pedidos", [
                        novo_id, unidade, "aberto",
                        usuario["nome"], datetime.datetime.now().isoformat(), "", "",
                    ])
                    for prod_id, qtd in itens_pedido.items():
                        append_linha("itens_pedido", [item_id, novo_id, prod_id, qtd])
                        item_id += 1
                    st.session_state["pedido_form_v"] += 1
                    st.cache_data.clear()
                    st.success(f"Solicitação #{novo_id} enviada para {unidade}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar solicitação: {e}")

with tab_abertos:
    if df_pedidos.empty:
        st.info("Nenhuma solicitação aberta.")
    else:
        pedidos_abertos = df_pedidos[df_pedidos["status"] == "aberto"]
        if unidades_acesso != "todos":
            pedidos_abertos = pedidos_abertos[pedidos_abertos["unidade"].isin(unidades_disponiveis)]

        if pedidos_abertos.empty:
            st.info("Nenhuma solicitação aberta para sua(s) unidade(s).")
        else:
            for _, ped in pedidos_abertos.iterrows():
                ped_id = _safe_int(ped["id"])
                data_label = str(ped.get("data_criacao", ""))[:10] or "—"
                with st.expander(f"#{ped_id} — {ped['unidade']} — {data_label}"):
                    itens = (
                        df_itens[df_itens["pedido_id"].apply(_safe_int) == ped_id]
                        if not df_itens.empty else pd.DataFrame()
                    )
                    if not itens.empty and not df_produtos.empty:
                        itens_display = itens.merge(
                            df_produtos[["id", "descricao", "unidade_base"]],
                            left_on="produto_id", right_on="id", how="left"
                        )[["descricao", "unidade_base", "quantidade"]]
                        st.dataframe(itens_display, use_container_width=True, hide_index=True)

                    if perfil in ["admin", "comprador"]:
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("Bloquear (consolidar)", key=f"bloquear_{ped_id}"):
                                idx = df_pedidos[df_pedidos["id"].apply(_safe_int) == ped_id].index[0]
                                df_pedidos.at[idx, "status"] = "bloqueado"
                                df_pedidos.at[idx, "data_bloqueio"] = datetime.datetime.now().isoformat()
                                escrever_df("pedidos", df_pedidos)
                                st.success("Pedido bloqueado!")
                                st.cache_data.clear()
                                st.rerun()
