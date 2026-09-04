import streamlit as st
import pandas as pd
import datetime
from modules.auth import requer_login
from modules.google_sheets import ler_df, escrever_df, append_linha

st.set_page_config(page_title="Pedidos", page_icon="📋", layout="wide")
usuario = requer_login()

st.title("📋 Solicitações de Compra")

df_produtos = ler_df("produtos")
df_pedidos = ler_df("pedidos")
df_itens = ler_df("itens_pedido")

perfil = usuario["perfil"]
unidades_acesso = usuario["unidades_acesso"]
if unidades_acesso == "todos":
    unidades_disponiveis = ler_df("unidades")["nome"].tolist()
else:
    unidades_disponiveis = [u.strip() for u in str(unidades_acesso).split(",")]

tab_novo, tab_abertos = st.tabs(["Nova Solicitação", "Solicitações Abertas"])

with tab_novo:
    unidade = st.selectbox("Unidade", unidades_disponiveis)

    produtos_ativos = df_produtos[df_produtos["ativo"] == True] if not df_produtos.empty else pd.DataFrame()

    if produtos_ativos.empty:
        st.warning("Nenhum produto ativo cadastrado.")
    else:
        st.markdown("Preencha a quantidade desejada. Deixe em branco os produtos que não precisa.")
        itens_pedido = {}
        for _, prod in produtos_ativos.iterrows():
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**{prod['descricao']}** — {prod['unidade_medida']}")
                if prod.get("observacao"):
                    st.caption(prod["observacao"])
            with col2:
                qtd = st.number_input("Qtd", min_value=0.0, step=0.5, key=f"qtd_{prod['id']}", label_visibility="collapsed")
                if qtd > 0:
                    itens_pedido[prod["id"]] = qtd

        if st.button("Enviar Solicitação", type="primary"):
            if not itens_pedido:
                st.error("Selecione ao menos um produto com quantidade.")
            else:
                novo_id = int(df_pedidos["id"].max()) + 1 if not df_pedidos.empty else 1
                append_linha("pedidos", [
                    novo_id, unidade, "aberto",
                    usuario["nome"], datetime.datetime.now().isoformat(), ""
                ])
                item_id = int(df_itens["id"].max()) + 1 if not df_itens.empty else 1
                for prod_id, qtd in itens_pedido.items():
                    append_linha("itens_pedido", [item_id, novo_id, prod_id, qtd])
                    item_id += 1
                st.success(f"Solicitação #{novo_id} enviada para {unidade}!")
                st.cache_resource.clear()
                st.rerun()

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
                with st.expander(f"#{ped['id']} — {ped['unidade']} — {ped['data_criacao'][:10]}"):
                    itens = df_itens[df_itens["pedido_id"] == ped["id"]]
                    if not itens.empty and not df_produtos.empty:
                        itens_display = itens.merge(
                            df_produtos[["id", "descricao", "unidade_medida"]],
                            left_on="produto_id", right_on="id", how="left"
                        )[["descricao", "unidade_medida", "quantidade"]]
                        st.dataframe(itens_display, use_container_width=True, hide_index=True)

                    if perfil in ["admin", "comprador"]:
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("Bloquear (consolidar)", key=f"bloquear_{ped['id']}"):
                                idx = df_pedidos[df_pedidos["id"] == ped["id"]].index[0]
                                df_pedidos.at[idx, "status"] = "bloqueado"
                                df_pedidos.at[idx, "data_bloqueio"] = datetime.datetime.now().isoformat()
                                escrever_df("pedidos", df_pedidos)
                                st.success("Pedido bloqueado!")
                                st.cache_resource.clear()
                                st.rerun()
