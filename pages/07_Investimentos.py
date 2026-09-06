import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import date
from src import auth, sheets as sh, utils

st.set_page_config(page_title="Investimentos — FinTrack", page_icon="📈", layout="wide")
auth.require_auth()

st.title("📈 Investimentos")

tabs = st.tabs(["Portfólio", "Novo Investimento", "Retirada", "Simulador", "Comparativo"])

TIPOS = ["CDB", "Tesouro Direto", "LCI", "LCA", "Poupança", "Fundos", "Ações", "Outro"]
TAXA_TIPOS = ["MENSAL", "ANUAL", "CDI"]

# ─── Portfólio ────────────────────────────────────────────────────────────────

with tabs[0]:
    df = sh.get_investimentos("ATIVO")
    df_ret = sh.get_investimentos("RETIRADO")

    if df.empty:
        st.info("Nenhum investimento ativo.")
    else:
        # Totais
        total_aplicado = df["valor_aplicado"].astype(float).sum()
        hoje = date.today().isoformat()
        total_atual = 0.0
        for _, row in df.iterrows():
            res = utils.calcular_rendimento(
                float(row["valor_aplicado"]), row["taxa_tipo"],
                float(row["taxa_valor"]), row["data_aplicacao"], hoje
            )
            total_atual += res["valor_final"]

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total Aplicado", utils.fmt_brl(total_aplicado))
        with c2:
            st.metric("Valor Atual Estimado", utils.fmt_brl(total_atual))
        with c3:
            rendimento_total = total_atual - total_aplicado
            st.metric("Rendimento Total", utils.fmt_brl(rendimento_total),
                      delta=f"{(rendimento_total/total_aplicado*100):.2f}%" if total_aplicado else "0%")

        st.markdown("---")

        # Gráfico de composição
        fig = px.pie(df, values=df["valor_aplicado"].astype(float),
                     names="nome", title="Composição do Portfólio")
        st.plotly_chart(fig, use_container_width=True)

        # Lista de investimentos
        for _, row in df.iterrows():
            res = utils.calcular_rendimento(
                float(row["valor_aplicado"]), row["taxa_tipo"],
                float(row["taxa_valor"]), row["data_aplicacao"], hoje
            )
            with st.expander(f"📊 {row['nome']} ({row['tipo']})"):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("Aplicado em", utils.fmt_data(row["data_aplicacao"]))
                    st.metric("Valor aplicado", utils.fmt_brl(float(row["valor_aplicado"])))
                with c2:
                    taxa_str = f"{row['taxa_valor']}% {row['taxa_tipo']}"
                    if row["taxa_tipo"] == "CDI":
                        taxa_str = f"{row['taxa_valor']}% do CDI"
                    st.metric("Taxa", taxa_str)
                    st.metric("Vencimento", utils.fmt_data(row["data_vencimento"]) if row["data_vencimento"] else "—")
                with c3:
                    st.metric("Valor atual", utils.fmt_brl(res["valor_final"]))
                    st.metric("Rendimento", utils.fmt_brl(res["rendimento"]))
                with c4:
                    st.metric("Rentabilidade", utils.fmt_pct(res["rentabilidade_pct"]))
                    st.metric("Meses aplicado", str(res["meses"]))

    # Investimentos retirados
    if not df_ret.empty:
        with st.expander("📋 Investimentos Encerrados"):
            for _, row in df_ret.iterrows():
                if row["valor_retirado"]:
                    lucro = float(row["valor_retirado"]) - float(row["valor_aplicado"])
                    st.write(f"**{row['nome']}**: {utils.fmt_brl(float(row['valor_aplicado']))} → "
                             f"{utils.fmt_brl(float(row['valor_retirado']))} "
                             f"(lucro: {utils.fmt_brl(lucro)})")

# ─── Novo Investimento ────────────────────────────────────────────────────────

with tabs[1]:
    with st.form("form_invest"):
        c1, c2 = st.columns(2)
        with c1:
            nome_i = st.text_input("Nome / Banco (ex: CDB Nubank)")
            tipo_i = st.selectbox("Tipo", TIPOS)
            data_aplic = st.date_input("Data da aplicação", value=date.today(), format="DD/MM/YYYY")
            valor_aplic = st.number_input("Valor aplicado (R$)", min_value=0.01, step=0.01, format="%.2f")
        with c2:
            taxa_tipo = st.selectbox("Tipo de taxa", TAXA_TIPOS)
            taxa_val = st.number_input(
                "Taxa (%)" if taxa_tipo != "CDI" else "% do CDI (ex: 100 = 100% CDI)",
                min_value=0.0, step=0.01, format="%.4f"
            )
            data_venc = st.date_input("Data de vencimento prevista", format="DD/MM/YYYY")
        submitted = st.form_submit_button("Salvar Investimento", use_container_width=True)

    if submitted and nome_i:
        sh.add_investimento(nome_i.strip(), tipo_i, data_aplic.isoformat(),
                            valor_aplic, taxa_tipo, taxa_val, data_venc.isoformat())
        st.success(f"Investimento '{nome_i}' cadastrado!")
        st.rerun()

# ─── Retirada ────────────────────────────────────────────────────────────────

with tabs[2]:
    df_ativos = sh.get_investimentos("ATIVO")
    if df_ativos.empty:
        st.info("Nenhum investimento ativo para retirar.")
    else:
        opcoes_inv = df_ativos["nome"].tolist()
        invest_sel = st.selectbox("Selecione o investimento", opcoes_inv)
        row_i = df_ativos[df_ativos["nome"] == invest_sel].iloc[0]

        # Valor estimado atual
        res_est = utils.calcular_rendimento(
            float(row_i["valor_aplicado"]), row_i["taxa_tipo"],
            float(row_i["taxa_valor"]), row_i["data_aplicacao"]
        )
        st.info(f"Valor estimado atual: **{utils.fmt_brl(res_est['valor_final'])}** "
                f"(rendimento: {utils.fmt_brl(res_est['rendimento'])})")

        with st.form("form_retirada"):
            c1, c2 = st.columns(2)
            with c1:
                data_ret = st.date_input("Data da retirada", value=date.today(), format="DD/MM/YYYY")
                valor_ret = st.number_input("Valor efetivamente recebido (R$)",
                                            value=res_est["valor_final"],
                                            min_value=0.01, step=0.01, format="%.2f")
            with c2:
                contas_df = sh.get_contas()
                contas = contas_df["nome"].tolist() if not contas_df.empty else []
                conta_dest = st.selectbox("Depositar em qual conta?", contas) if contas else st.text_input("Conta")
                fontes_df = sh.get_fontes()
            submitted_ret = st.form_submit_button("Registrar Retirada", use_container_width=True)

        if submitted_ret:
            sh.retirar_investimento(row_i["id"], valor_ret, data_ret.isoformat())
            sh.add_entrada(data_ret.isoformat(), valor_ret,
                           "Retirada de Investimento", conta_dest,
                           f"Retirada: {invest_sel}")
            lucro = valor_ret - float(row_i["valor_aplicado"])
            st.success(f"Retirada registrada! Lucro: {utils.fmt_brl(lucro)}")
            st.rerun()

# ─── Simulador ────────────────────────────────────────────────────────────────

with tabs[3]:
    st.subheader("📊 Simulador de Crescimento")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        sim_inicial = st.number_input("Valor inicial (R$)", value=1000.0, min_value=0.0, step=100.0, format="%.2f")
    with c2:
        sim_aporte = st.number_input("Aporte mensal (R$)", value=200.0, min_value=0.0, step=50.0, format="%.2f")
    with c3:
        sim_taxa_tipo = st.selectbox("Tipo de taxa", TAXA_TIPOS, key="sim_tt")
        sim_taxa = st.number_input("Taxa", value=1.0, min_value=0.0, step=0.01, format="%.4f", key="sim_tv")
    with c4:
        sim_meses = st.slider("Período (meses)", 1, 240, 24)

    if sim_taxa_tipo == "MENSAL":
        tm = sim_taxa / 100
    elif sim_taxa_tipo == "ANUAL":
        tm = (1 + sim_taxa / 100) ** (1 / 12) - 1
    else:
        tm = 0.009 * (sim_taxa / 100)

    resultado_sim = utils.simular_investimento(sim_inicial, sim_aporte, tm, sim_meses)
    df_sim = pd.DataFrame(resultado_sim)

    col_m1, col_m2, col_m3 = st.columns(3)
    ultimo = df_sim.iloc[-1]
    with col_m1:
        st.metric("Saldo Final", utils.fmt_brl(ultimo["saldo"]))
    with col_m2:
        st.metric("Total Investido", utils.fmt_brl(ultimo["total_investido"]))
    with col_m3:
        st.metric("Rendimento Total", utils.fmt_brl(ultimo["rendimento"]))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_sim["mes"], y=df_sim["saldo"],
                              name="Saldo", fill="tozeroy", line=dict(color="#2ECC71")))
    fig.add_trace(go.Scatter(x=df_sim["mes"], y=df_sim["total_investido"],
                              name="Total investido", line=dict(color="#3498DB", dash="dash")))
    fig.update_layout(title="Evolução do Investimento", xaxis_title="Meses",
                      yaxis_title="R$", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

# ─── Comparativo ─────────────────────────────────────────────────────────────

with tabs[4]:
    st.subheader("⚖️ Comparativo de Investimentos")
    c1, c2 = st.columns(2)
    with c1:
        comp_valor = st.number_input("Valor a investir (R$)", value=5000.0, step=100.0, format="%.2f")
    with c2:
        comp_meses = st.slider("Período (meses)", 1, 120, 12)

    st.markdown("**Configure as opções para comparar:**")
    opcoes = [
        {"nome": "CDB 12% a.a.", "taxa_tipo": "ANUAL", "taxa_valor": 12.0},
        {"nome": "100% CDI", "taxa_tipo": "CDI", "taxa_valor": 100.0},
        {"nome": "Poupança (0.5% a.m.)", "taxa_tipo": "MENSAL", "taxa_valor": 0.5},
        {"nome": "Tesouro Selic (CDI+0.01%)", "taxa_tipo": "CDI", "taxa_valor": 101.0},
    ]

    resultado_comp = utils.comparar_investimentos(comp_valor, comp_meses, opcoes)
    df_comp = pd.DataFrame(resultado_comp)

    fig_comp = px.bar(df_comp, x="nome", y="valor_final", color="nome",
                      text=df_comp["valor_final"].apply(utils.fmt_brl),
                      title="Comparativo de Rendimentos",
                      color_discrete_sequence=px.colors.qualitative.Set2)
    fig_comp.update_traces(textposition="outside")
    fig_comp.update_layout(showlegend=False, template="plotly_dark",
                            yaxis_title="Valor Final (R$)")
    st.plotly_chart(fig_comp, use_container_width=True)

    st.dataframe(df_comp.rename(columns={
        "nome": "Investimento", "valor_final": "Valor Final",
        "rendimento": "Rendimento", "rentabilidade_pct": "Rentabilidade (%)"
    }), hide_index=True, use_container_width=True)
