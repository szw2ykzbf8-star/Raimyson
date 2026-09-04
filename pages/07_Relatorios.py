import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
from modules.auth import requer_perfil
from modules.google_sheets import ler_df

st.set_page_config(page_title="Relatórios", page_icon="📈", layout="wide")
usuario = requer_perfil(["admin", "comprador"])

st.title("📈 Relatórios e Análises")

df_hist = ler_df("historico_precos")
df_produtos = ler_df("produtos")
df_fornecedores = ler_df("fornecedores")
df_compras = ler_df("compras")
df_itens_compra = ler_df("itens_compra")
df_pedidos = ler_df("pedidos")
df_itens_pedido = ler_df("itens_pedido")
df_orcamentos = ler_df("orcamentos")

if df_hist.empty or df_compras.empty:
    st.info("Ainda não há dados suficientes para gerar relatórios. Realize ao menos uma compra.")
    st.stop()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Compras por Período",
    "Evolução de Preços",
    "Consumo por Produto",
    "Desempenho de Fornecedores",
    "Orçamento vs Gasto"
])

with tab1:
    st.subheader("Compras por Período")
    col1, col2, col3 = st.columns(3)
    with col1:
        data_ini = st.date_input("De", value=datetime.date.today().replace(day=1))
    with col2:
        data_fim = st.date_input("Até", value=datetime.date.today())
    with col3:
        unidade_filtro = st.selectbox("Unidade", ["Todas"] + df_pedidos["unidade"].unique().tolist() if not df_pedidos.empty else ["Todas"])

    compras_periodo = df_compras.copy()
    compras_periodo["data_compra"] = pd.to_datetime(compras_periodo["data_compra"])
    compras_periodo = compras_periodo[
        (compras_periodo["data_compra"].dt.date >= data_ini) &
        (compras_periodo["data_compra"].dt.date <= data_fim)
    ]

    if compras_periodo.empty:
        st.info("Nenhuma compra no período selecionado.")
    else:
        total = compras_periodo["valor_total"].astype(float).sum()
        st.metric("Total gasto no período", f"R$ {total:,.2f}")

        fig = px.bar(
            compras_periodo.merge(df_fornecedores[["id", "razao_social"]], left_on="fornecedor_id", right_on="id"),
            x="razao_social", y="valor_total", title="Gasto por Fornecedor",
            labels={"razao_social": "Fornecedor", "valor_total": "Valor (R$)"},
            color="razao_social"
        )
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Evolução de Preço por Produto")
    if not df_hist.empty and not df_produtos.empty:
        prod_opcoes = df_produtos[df_produtos["ativo"] == True][["id", "descricao"]]
        prod_sel = st.selectbox(
            "Produto",
            options=prod_opcoes["id"].tolist(),
            format_func=lambda x: prod_opcoes[prod_opcoes["id"] == x]["descricao"].values[0]
        )

        hist_prod = df_hist[df_hist["produto_id"] == prod_sel].copy()
        hist_prod["data"] = pd.to_datetime(hist_prod["data"])
        hist_prod = hist_prod.merge(df_fornecedores[["id", "razao_social"]], left_on="fornecedor_id", right_on="id", how="left")

        if hist_prod.empty:
            st.info("Sem histórico para este produto.")
        else:
            fig = px.line(
                hist_prod, x="data", y="preco_normalizado",
                color="razao_social", markers=True,
                title="Evolução do Preço Normalizado por Fornecedor",
                labels={"data": "Data", "preco_normalizado": "Preço (R$)", "razao_social": "Fornecedor"}
            )
            ganhou = hist_prod[hist_prod["ganhou"] == True]
            fig.add_scatter(x=ganhou["data"], y=ganhou["preco_normalizado"], mode="markers",
                           marker=dict(size=12, symbol="star", color="gold"), name="Vencedor")
            st.plotly_chart(fig, use_container_width=True)

            variacao = hist_prod.groupby("data")["preco_normalizado"].min()
            if len(variacao) > 1:
                crescimento = ((variacao.iloc[-1] - variacao.iloc[0]) / variacao.iloc[0]) * 100
                cor = "🔴" if crescimento > 0 else "🟢"
                st.metric("Variação total de preço", f"{crescimento:+.1f}%", delta=f"{cor}")

with tab3:
    st.subheader("Consumo por Produto")
    if not df_itens_compra.empty and not df_produtos.empty:
        consumo = df_itens_compra.merge(df_produtos[["id", "descricao"]], left_on="produto_id", right_on="id")
        consumo["quantidade"] = consumo["quantidade"].astype(float)
        consumo_total = consumo.groupby("descricao")["quantidade"].sum().reset_index()
        consumo_total = consumo_total.sort_values("quantidade", ascending=False)

        fig = px.bar(consumo_total.head(20), x="descricao", y="quantidade",
                    title="Top 20 Produtos Mais Comprados (por quantidade)",
                    labels={"descricao": "Produto", "quantidade": "Quantidade Total"})
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Mais consumidos**")
            st.dataframe(consumo_total.head(10), hide_index=True, use_container_width=True)
        with col2:
            st.markdown("**Menos consumidos**")
            st.dataframe(consumo_total.tail(10), hide_index=True, use_container_width=True)

with tab4:
    st.subheader("Desempenho de Fornecedores")
    if not df_hist.empty and not df_fornecedores.empty:
        vitorias = df_hist[df_hist["ganhou"] == True].groupby("fornecedor_id").size().reset_index(name="vitorias")
        total_part = df_hist.groupby("fornecedor_id").size().reset_index(name="participacoes")
        desemp = vitorias.merge(total_part, on="fornecedor_id")
        desemp["taxa_vitoria"] = (desemp["vitorias"] / desemp["participacoes"] * 100).round(1)
        desemp = desemp.merge(df_fornecedores[["id", "razao_social"]], left_on="fornecedor_id", right_on="id")

        fig = px.bar(desemp.sort_values("taxa_vitoria", ascending=False),
                    x="razao_social", y="taxa_vitoria",
                    title="Taxa de Vitória por Fornecedor (%)",
                    labels={"razao_social": "Fornecedor", "taxa_vitoria": "Taxa de Vitória (%)"})
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(desemp[["razao_social", "participacoes", "vitorias", "taxa_vitoria"]].sort_values("taxa_vitoria", ascending=False),
                    hide_index=True, use_container_width=True)

with tab5:
    st.subheader("Orçamento vs Gasto por Unidade")
    if not df_orcamentos.empty:
        mes_atual = datetime.date.today().month
        ano_atual = datetime.date.today().year
        col1, col2 = st.columns(2)
        with col1:
            mes_sel = st.selectbox("Mês", range(1, 13), index=mes_atual - 1)
        with col2:
            ano_sel = st.number_input("Ano", value=ano_atual, min_value=2020, max_value=2099)

        orc_mes = df_orcamentos[(df_orcamentos["mes"] == mes_sel) & (df_orcamentos["ano"] == ano_sel)]

        compras_mes = df_compras.copy()
        compras_mes["data_compra"] = pd.to_datetime(compras_mes["data_compra"])
        compras_mes = compras_mes[
            (compras_mes["data_compra"].dt.month == mes_sel) &
            (compras_mes["data_compra"].dt.year == ano_sel)
        ]

        if orc_mes.empty:
            st.info("Nenhum orçamento cadastrado para este período.")
        else:
            dados = []
            for _, orc in orc_mes.iterrows():
                gasto = compras_mes["valor_total"].astype(float).sum()
                dados.append({
                    "Unidade": orc["unidade"],
                    "Orçamento": float(orc["valor"]),
                    "Gasto": gasto,
                    "Saldo": float(orc["valor"]) - gasto
                })

            df_orc = pd.DataFrame(dados)
            fig = go.Figure()
            fig.add_bar(x=df_orc["Unidade"], y=df_orc["Orçamento"], name="Orçamento")
            fig.add_bar(x=df_orc["Unidade"], y=df_orc["Gasto"], name="Gasto")
            fig.update_layout(barmode="group", title="Orçamento vs Gasto por Unidade")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_orc, hide_index=True, use_container_width=True)
    else:
        st.info("Configure os orçamentos na página de Configurações.")
