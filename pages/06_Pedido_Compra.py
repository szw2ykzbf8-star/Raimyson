import streamlit as st
import pandas as pd
import datetime
from modules.auth import requer_perfil
from modules.google_sheets import ler_df, escrever_df

st.set_page_config(page_title="Pedidos de Compra", page_icon="🛒", layout="wide")
usuario = requer_perfil(["admin", "comprador"])

st.title("🛒 Pedidos de Compra")

df_compras = ler_df("compras")
df_itens_compra = ler_df("itens_compra")
df_fornecedores = ler_df("fornecedores")
df_produtos = ler_df("produtos")
df_pedidos = ler_df("pedidos")
df_itens_pedido = ler_df("itens_pedido")
df_unidades = ler_df("unidades")

compras_pendentes = df_compras[df_compras["pedido_gerado"] == False] if not df_compras.empty else pd.DataFrame()

if compras_pendentes.empty:
    st.info("Nenhum pedido de compra pendente para envio.")
else:
    for _, compra in compras_pendentes.iterrows():
        forn_info = df_fornecedores[df_fornecedores["id"] == compra["fornecedor_id"]]
        if forn_info.empty:
            continue
        forn = forn_info.iloc[0]

        with st.expander(f"Pedido #{compra['id']} — {forn['razao_social']} — R$ {float(compra['valor_total']):.2f}"):
            itens = df_itens_compra[df_itens_compra["compra_id"] == compra["id"]]

            linhas = []
            for _, item in itens.iterrows():
                prod_info = df_produtos[df_produtos["id"] == item["produto_id"]]
                if prod_info.empty:
                    continue
                prod = prod_info.iloc[0]

                itens_ped = df_itens_pedido[df_itens_pedido["produto_id"] == item["produto_id"]]
                por_unidade = {}
                for _, ip in itens_ped.iterrows():
                    ped = df_pedidos[df_pedidos["id"] == ip["pedido_id"]]
                    if not ped.empty:
                        unidade = ped.iloc[0]["unidade"]
                        por_unidade[unidade] = ip["quantidade"]

                linhas.append({
                    "Produto": prod["descricao"],
                    "Unidade Medida": prod["unidade_medida"],
                    "Qtd Total": item["quantidade"],
                    "Preço Unit.": f"R$ {float(item['preco_unitario']):.2f}",
                    "Subtotal": f"R$ {float(item['preco_unitario']) * float(item['quantidade']):.2f}",
                    **{f"↳ {k}": v for k, v in por_unidade.items()}
                })

            if linhas:
                df_display = pd.DataFrame(linhas)
                st.dataframe(df_display, use_container_width=True, hide_index=True)

            st.markdown(f"**Total: R$ {float(compra['valor_total']):.2f}**")

            texto_whats = f"*Pedido de Compra #{compra['id']} — H Hotéis*\n"
            texto_whats += f"Data: {compra['data_compra']}\n\n"
            for linha in linhas:
                texto_whats += f"• {linha['Produto']} ({linha['Unidade Medida']}): {linha['Qtd Total']} unid — {linha['Preço Unit.']}\n"
                for k, v in linha.items():
                    if k.startswith("↳"):
                        texto_whats += f"  {k}: {v}\n"
            texto_whats += f"\n*Total: R$ {float(compra['valor_total']):.2f}*"

            st.text_area("Texto para WhatsApp (copie e envie)", value=texto_whats, height=200, key=f"whats_{compra['id']}")

            col1, col2 = st.columns(2)
            with col1:
                tel = str(forn.get("telefone", "")).replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                if tel:
                    st.markdown(f"📱 Contato: **{forn['nome_contato']}** — {forn['telefone']}")

            with col2:
                if st.button("Marcar como Enviado", key=f"enviado_{compra['id']}"):
                    idx = df_compras[df_compras["id"] == compra["id"]].index[0]
                    df_compras.at[idx, "pedido_gerado"] = True
                    escrever_df("compras", df_compras)
                    st.success("Pedido marcado como enviado!")
                    st.cache_resource.clear()
                    st.rerun()
