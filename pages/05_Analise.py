import streamlit as st
import pandas as pd
import datetime
from modules.auth import requer_perfil
from modules.google_sheets import ler_df, escrever_df, append_linha

st.set_page_config(page_title="Análise de Preços", page_icon="📊", layout="wide")
usuario = requer_perfil(["admin", "comprador"])

st.title("📊 Análise de Preços")


def preco_normalizado(preco, tipo, qtd_emb):
    try:
        preco = float(preco)
        qtd_emb = float(qtd_emb) if qtd_emb else 1
    except (ValueError, TypeError):
        return preco
    if tipo == "Fardo/Caixa" and qtd_emb > 1:
        return preco / qtd_emb
    return preco


df_cotacoes = ler_df("cotacoes")
df_respostas = ler_df("respostas")
df_produtos = ler_df("produtos")
df_fornecedores = ler_df("fornecedores")
df_pedidos = ler_df("pedidos")
df_itens = ler_df("itens_pedido")

cotacoes_encerradas = df_cotacoes[df_cotacoes["status"] == "encerrada"] if not df_cotacoes.empty else pd.DataFrame()

if cotacoes_encerradas.empty:
    st.info("Nenhuma cotação encerrada aguardando análise.")
else:
    cotacao_sel = st.selectbox(
        "Selecione a cotação para analisar",
        options=cotacoes_encerradas["id"].tolist(),
        format_func=lambda x: f"Cotação #{x}"
    )

    respostas = df_respostas[df_respostas["cotacao_id"] == cotacao_sel] if not df_respostas.empty else pd.DataFrame()

    if respostas.empty:
        st.warning("Nenhuma resposta de fornecedor para esta cotação.")
    else:
        produtos_ids = respostas["produto_id"].unique()

        st.markdown("---")
        st.subheader("Comparativo de Preços")
        st.caption("Ajuste o fator multiplicador se necessário antes de selecionar o vencedor.")

        selecoes = {}

        for prod_id in produtos_ids:
            prod_info = df_produtos[df_produtos["id"] == prod_id]
            if prod_info.empty:
                continue
            prod_nome = prod_info.iloc[0]["descricao"]
            prod_unidade = prod_info.iloc[0]["unidade_medida"]

            resps_prod = respostas[respostas["produto_id"] == prod_id].copy()

            st.markdown(f"#### {prod_nome} — {prod_unidade}")

            tabela = []
            for _, resp in resps_prod.iterrows():
                forn_info = df_fornecedores[df_fornecedores["id"] == resp["fornecedor_id"]]
                forn_nome = forn_info.iloc[0]["razao_social"] if not forn_info.empty else str(resp["fornecedor_id"])

                col_forn, col_preco, col_tipo, col_qtd, col_fator, col_norm, col_obs = st.columns([2, 1, 1.5, 1, 1, 1.2, 2])
                with col_forn:
                    st.write(forn_nome)
                with col_preco:
                    st.write(f"R$ {float(resp['preco']):.2f}")
                with col_tipo:
                    st.write(resp["tipo_embalagem"])
                with col_qtd:
                    st.write(str(resp.get("qtd_por_embalagem", "—")))
                with col_fator:
                    fator = st.number_input(
                        "Fator", value=1.0, min_value=0.01, step=0.5,
                        key=f"fator_{prod_id}_{resp['fornecedor_id']}",
                        label_visibility="collapsed"
                    )
                with col_norm:
                    p_norm = float(resp["preco"]) / fator if fator > 0 else float(resp["preco"])
                    st.write(f"**R$ {p_norm:.2f}**")
                with col_obs:
                    st.caption(str(resp.get("observacao", "")))

                tabela.append({
                    "fornecedor_id": resp["fornecedor_id"],
                    "nome": forn_nome,
                    "preco": float(resp["preco"]),
                    "preco_norm": p_norm,
                    "fator": fator,
                    "tipo": resp["tipo_embalagem"],
                    "qtd_emb": resp.get("qtd_por_embalagem", 1),
                })

            if tabela:
                melhor = min(tabela, key=lambda x: x["preco_norm"])
                st.success(f"✅ Melhor preço normalizado: **{melhor['nome']}** — R$ {melhor['preco_norm']:.2f}")

                opcoes = {r["fornecedor_id"]: r["nome"] for r in tabela}
                vencedor = st.selectbox(
                    "Selecionar vencedor",
                    options=list(opcoes.keys()),
                    format_func=lambda x: opcoes[x],
                    index=list(opcoes.keys()).index(melhor["fornecedor_id"]),
                    key=f"venc_{prod_id}"
                )

                qtd_total = df_itens[df_itens["produto_id"] == prod_id]["quantidade"].sum()
                qtd_ajustada = st.number_input(
                    f"Quantidade final ({prod_unidade})",
                    value=float(qtd_total), min_value=0.0, step=0.5,
                    key=f"qtd_final_{prod_id}"
                )

                selecoes[prod_id] = {
                    "fornecedor_id": vencedor,
                    "quantidade": qtd_ajustada,
                    "preco": next(r["preco"] for r in tabela if r["fornecedor_id"] == vencedor),
                    "preco_norm": next(r["preco_norm"] for r in tabela if r["fornecedor_id"] == vencedor),
                    "fator": next(r["fator"] for r in tabela if r["fornecedor_id"] == vencedor),
                }

            st.markdown("---")

        if selecoes and st.button("Finalizar Compra e Gerar Pedidos", type="primary"):
            df_compras = ler_df("compras")
            df_itens_compra = ler_df("itens_compra")
            df_hist = ler_df("historico_precos")

            fornecedores_vencedores = {}
            for prod_id, sel in selecoes.items():
                fid = sel["fornecedor_id"]
                if fid not in fornecedores_vencedores:
                    fornecedores_vencedores[fid] = []
                fornecedores_vencedores[fid].append((prod_id, sel))

            compra_id = int(df_compras["id"].max()) + 1 if not df_compras.empty else 1
            item_compra_id = int(df_itens_compra["id"].max()) + 1 if not df_itens_compra.empty else 1
            hist_id = int(df_hist["id"].max()) + 1 if not df_hist.empty else 1

            for fid, itens in fornecedores_vencedores.items():
                valor_total = sum(s["preco_norm"] * s["quantidade"] for _, s in itens)
                append_linha("compras", [compra_id, cotacao_sel, fid, datetime.date.today().isoformat(), round(valor_total, 2), False])

                for prod_id, sel in itens:
                    append_linha("itens_compra", [
                        item_compra_id, compra_id, prod_id,
                        sel["quantidade"], sel["preco"], sel["preco_norm"], sel["fator"]
                    ])
                    item_compra_id += 1

                compra_id += 1

            for prod_id, sel in selecoes.items():
                for _, resp in respostas[respostas["produto_id"] == prod_id].iterrows():
                    ganhou = resp["fornecedor_id"] == sel["fornecedor_id"]
                    append_linha("historico_precos", [
                        hist_id, prod_id, resp["fornecedor_id"], cotacao_sel,
                        resp["preco"], resp["tipo_embalagem"], resp.get("qtd_por_embalagem", 1),
                        round(preco_normalizado(resp["preco"], resp["tipo_embalagem"], resp.get("qtd_por_embalagem", 1)), 4),
                        ganhou, datetime.date.today().isoformat()
                    ])
                    hist_id += 1

            idx = df_cotacoes[df_cotacoes["id"] == cotacao_sel].index[0]
            df_cotacoes.at[idx, "status"] = "finalizada"
            escrever_df("cotacoes", df_cotacoes)

            st.success("Compra finalizada! Acesse a página de Pedidos de Compra para enviar via WhatsApp.")
            st.cache_resource.clear()
            st.rerun()
