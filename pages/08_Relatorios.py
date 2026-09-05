import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from src import auth, sheets as sh, utils

st.set_page_config(page_title="Relatórios — FinTrack", page_icon="📉", layout="wide")
auth.require_auth()

st.title("📉 Relatórios & Análises")

tabs = st.tabs(["Fluxo Mensal", "Categorias", "Cartões", "Investimentos", "Avançado"])

# ─── Helpers ─────────────────────────────────────────────────────────────────

def safe_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def build_monthly_data(n_meses: int = 12):
    meses = utils.ultimos_meses(n_meses)
    rows = []
    for m in meses:
        ent = sh.get_entradas(m)
        gas = sh.get_gastos(m)
        total_e = ent["valor"].apply(safe_float).sum() if not ent.empty else 0
        total_g = gas["valor_parcela"].apply(safe_float).sum() if not gas.empty else 0
        rows.append({"mes": m, "label": utils.formatar_mes(m)[:7],
                     "entradas": total_e, "gastos": total_g, "saldo": total_e - total_g})
    return pd.DataFrame(rows)


# ─── Fluxo Mensal ────────────────────────────────────────────────────────────

with tabs[0]:
    n = st.slider("Últimos N meses", 3, 24, 12, key="sl_fluxo")
    df_m = build_monthly_data(n)

    # Barras: entradas vs gastos
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(x=df_m["label"], y=df_m["entradas"],
                           name="Entradas", marker_color="#2ECC71"))
    fig1.add_trace(go.Bar(x=df_m["label"], y=df_m["gastos"],
                           name="Gastos", marker_color="#E74C3C"))
    fig1.update_layout(barmode="group", title="Entradas × Gastos por Mês",
                       template="plotly_dark", xaxis_title="Mês", yaxis_title="R$")
    st.plotly_chart(fig1, use_container_width=True)

    # Saldo acumulado
    df_m["saldo_acum"] = df_m["saldo"].cumsum()
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df_m["label"], y=df_m["saldo"],
                               name="Saldo mensal", mode="lines+markers",
                               line=dict(color="#3498DB")))
    fig2.add_trace(go.Scatter(x=df_m["label"], y=df_m["saldo_acum"],
                               name="Saldo acumulado", mode="lines",
                               line=dict(color="#F39C12", dash="dash")))
    fig2.update_layout(title="Evolução do Saldo", template="plotly_dark",
                       xaxis_title="Mês", yaxis_title="R$")
    st.plotly_chart(fig2, use_container_width=True)

    # Tabela resumo
    df_show = df_m[["label", "entradas", "gastos", "saldo"]].copy()
    df_show["entradas"] = df_show["entradas"].apply(utils.fmt_brl)
    df_show["gastos"] = df_show["gastos"].apply(utils.fmt_brl)
    df_show["saldo"] = df_show["saldo"].apply(utils.fmt_brl)
    df_show.columns = ["Mês", "Entradas", "Gastos", "Saldo"]
    st.dataframe(df_show, use_container_width=True, hide_index=True)

# ─── Categorias ──────────────────────────────────────────────────────────────

with tabs[1]:
    mes_sel = st.session_state.get("mes_atual", utils.mes_atual())
    col_prev, col_mes, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button("◀", key="cat_prev"):
            st.session_state["mes_cat"] = utils.mes_anterior(
                st.session_state.get("mes_cat", mes_sel))
    with col_next:
        if st.button("▶", key="cat_next"):
            st.session_state["mes_cat"] = utils.proximo_mes(
                st.session_state.get("mes_cat", mes_sel))
    mes_cat = st.session_state.get("mes_cat", mes_sel)
    with col_mes:
        st.markdown(f"<h4 style='text-align:center'>{utils.formatar_mes(mes_cat)}</h4>",
                    unsafe_allow_html=True)

    df_cat_mes = sh.get_gastos(mes_cat)
    n_comp = st.slider("Comparar com últimos N meses", 1, 12, 3, key="sl_cat")
    meses_comp = utils.ultimos_meses(n_comp)

    if not df_cat_mes.empty:
        # Pizza: distribuição do mês
        cat_group = df_cat_mes.groupby("categoria")["valor_parcela"].apply(
            lambda s: s.apply(safe_float).sum()).reset_index()
        cat_group.columns = ["Categoria", "Valor"]
        fig_pizza = px.pie(cat_group, values="Valor", names="Categoria",
                           title=f"Gastos por Categoria — {utils.formatar_mes(mes_cat)}",
                           hole=0.4)
        fig_pizza.update_layout(template="plotly_dark")
        st.plotly_chart(fig_pizza, use_container_width=True)

        # Comparativo: mês atual vs média dos últimos N
        gastos_hist = []
        for m in meses_comp:
            dfm = sh.get_gastos(m)
            if not dfm.empty:
                gastos_hist.append(dfm)
        if gastos_hist:
            df_hist = pd.concat(gastos_hist)
            media_cat = df_hist.groupby("categoria")["valor_parcela"].apply(
                lambda s: s.apply(safe_float).mean()).reset_index()
            media_cat.columns = ["Categoria", "Média"]

            df_comp_cat = cat_group.merge(media_cat, on="Categoria", how="outer").fillna(0)
            fig_comp_cat = go.Figure()
            fig_comp_cat.add_trace(go.Bar(x=df_comp_cat["Categoria"], y=df_comp_cat["Valor"],
                                           name=utils.formatar_mes(mes_cat),
                                           marker_color="#E74C3C"))
            fig_comp_cat.add_trace(go.Bar(x=df_comp_cat["Categoria"], y=df_comp_cat["Média"],
                                           name=f"Média {n_comp} meses",
                                           marker_color="#3498DB"))
            fig_comp_cat.update_layout(barmode="group",
                                        title="Mês Atual × Média Histórica por Categoria",
                                        template="plotly_dark")
            st.plotly_chart(fig_comp_cat, use_container_width=True)
    else:
        st.info("Nenhum gasto neste mês.")

# ─── Cartões ─────────────────────────────────────────────────────────────────

with tabs[2]:
    cartoes_df = sh.get_cartoes()
    todos_gastos = sh.get_gastos()

    if cartoes_df.empty or todos_gastos.empty:
        st.info("Nenhum dado disponível.")
    else:
        # Comprometimento por cartão nos próximos 12 meses
        proximos = [utils.mes_atual()] + [
            utils.proximo_mes(utils.mes_str(
                int(utils.mes_atual()[:4]),
                int(utils.mes_atual()[5:7])
            ) if i == 0 else "")
            for i in range(11)
        ]
        # Gera lista de próximos 12 meses
        proximos_12 = []
        m = utils.mes_atual()
        for _ in range(12):
            proximos_12.append(m)
            m = utils.proximo_mes(m)

        rows_comp = []
        for cartao in cartoes_df["nome"].tolist():
            mask = (todos_gastos["conta_cartao"] == cartao) & \
                   (todos_gastos["forma_pagamento"] == "Crédito")
            df_c = todos_gastos[mask]
            for m in proximos_12:
                val = df_c[df_c["mes_referencia"] == m]["valor_parcela"].apply(safe_float).sum()
                rows_comp.append({"Cartão": cartao, "Mês": m, "Valor": val})

        df_faturas = pd.DataFrame(rows_comp)
        if not df_faturas.empty and df_faturas["Valor"].sum() > 0:
            fig_fat = px.bar(df_faturas, x="Mês", y="Valor", color="Cartão",
                             title="Faturas por Cartão — Próximos 12 Meses",
                             template="plotly_dark")
            st.plotly_chart(fig_fat, use_container_width=True)
        else:
            st.info("Nenhuma parcela futura registrada.")

        # Gasto total por cartão (histórico)
        gastos_por_cartao = todos_gastos[todos_gastos["forma_pagamento"] == "Crédito"]
        if not gastos_por_cartao.empty:
            gc = gastos_por_cartao.groupby("conta_cartao")["valor_parcela"].apply(
                lambda s: s.apply(safe_float).sum()).reset_index()
            gc.columns = ["Cartão", "Total Histórico"]
            fig_gc = px.bar(gc, x="Cartão", y="Total Histórico",
                            text=gc["Total Histórico"].apply(utils.fmt_brl),
                            title="Total Gasto por Cartão (Histórico)",
                            template="plotly_dark", color="Cartão")
            fig_gc.update_traces(textposition="outside")
            st.plotly_chart(fig_gc, use_container_width=True)

# ─── Investimentos ────────────────────────────────────────────────────────────

with tabs[3]:
    df_inv = sh.get_investimentos("ATIVO")
    df_inv_ret = sh.get_investimentos("RETIRADO")

    if not df_inv.empty:
        hoje = __import__("datetime").date.today().isoformat()
        dados_inv = []
        for _, row in df_inv.iterrows():
            res = utils.calcular_rendimento(
                float(row["valor_aplicado"]), row["taxa_tipo"],
                float(row["taxa_valor"]), row["data_aplicacao"], hoje
            )
            dados_inv.append({
                "Nome": row["nome"], "Tipo": row["tipo"],
                "Aplicado": float(row["valor_aplicado"]),
                "Atual": res["valor_final"],
                "Rendimento": res["rendimento"],
                "Rent%": res["rentabilidade_pct"],
            })
        df_inv_proc = pd.DataFrame(dados_inv)

        # Patrimônio por tipo
        fig_tipo = px.treemap(df_inv_proc, path=["Tipo", "Nome"],
                              values="Atual", title="Distribuição do Patrimônio",
                              template="plotly_dark")
        st.plotly_chart(fig_tipo, use_container_width=True)

        # Rentabilidade comparada
        fig_rent = px.bar(df_inv_proc, x="Nome", y="Rent%", color="Tipo",
                          title="Rentabilidade por Investimento (%)",
                          text=df_inv_proc["Rent%"].apply(lambda x: f"{x:.2f}%"),
                          template="plotly_dark")
        fig_rent.update_traces(textposition="outside")
        st.plotly_chart(fig_rent, use_container_width=True)
    else:
        st.info("Nenhum investimento ativo.")

# ─── Avançado ────────────────────────────────────────────────────────────────

with tabs[4]:
    st.subheader("🔬 Análises Avançadas")
    n_adv = st.slider("Análisar últimos N meses", 3, 24, 6, key="sl_adv")
    df_adv = build_monthly_data(n_adv)

    if len(df_adv) < 3:
        st.info("Acumule pelo menos 3 meses de dados para análises avançadas.")
    else:
        # Previsão simples por média móvel
        st.subheader("📊 Previsão de Gastos (Próximo Mês)")
        media_gastos = df_adv["gastos"].mean()
        std_gastos = df_adv["gastos"].std()
        st.metric("Previsão (média histórica)", utils.fmt_brl(media_gastos))
        st.caption(f"Desvio padrão: {utils.fmt_brl(std_gastos)}")
        st.info(f"Intervalo provável: {utils.fmt_brl(max(0, media_gastos - std_gastos))} "
                f"– {utils.fmt_brl(media_gastos + std_gastos)}")

        # Heatmap: gastos por categoria × mês
        st.subheader("🗓️ Heatmap de Gastos por Categoria")
        meses_heat = utils.ultimos_meses(n_adv)
        cats_df = sh.get_categorias()
        cats = cats_df["nome"].tolist() if not cats_df.empty else []

        heat_data = {}
        for m in meses_heat:
            dfm = sh.get_gastos(m)
            if dfm.empty:
                heat_data[m] = {c: 0 for c in cats}
            else:
                gc = dfm.groupby("categoria")["valor_parcela"].apply(
                    lambda s: s.apply(safe_float).sum())
                heat_data[m] = {c: gc.get(c, 0) for c in cats}

        df_heat = pd.DataFrame(heat_data, index=cats).T
        if not df_heat.empty:
            fig_heat = px.imshow(df_heat.values,
                                  x=cats, y=[utils.formatar_mes(m)[:7] for m in meses_heat],
                                  color_continuous_scale="RdYlGn_r",
                                  title="Intensidade de Gasto por Categoria (R$)",
                                  aspect="auto")
            fig_heat.update_layout(template="plotly_dark")
            st.plotly_chart(fig_heat, use_container_width=True)

        # Anomalias
        st.subheader("🚨 Detecção de Anomalias")
        mes_atual = utils.mes_atual()
        df_atual = sh.get_gastos(mes_atual)
        if not df_atual.empty:
            for cat in cats:
                vals_hist = []
                for m in meses_heat[:-1]:
                    dfm = sh.get_gastos(m)
                    if not dfm.empty:
                        v = dfm[dfm["categoria"] == cat]["valor_parcela"].apply(safe_float).sum()
                        vals_hist.append(v)
                if vals_hist:
                    media_h = np.mean(vals_hist)
                    val_atual = df_atual[df_atual["categoria"] == cat]["valor_parcela"].apply(safe_float).sum()
                    if media_h > 0 and val_atual > media_h * 2:
                        multiplo = val_atual / media_h
                        st.warning(f"⚠️ **{cat}**: {utils.fmt_brl(val_atual)} "
                                   f"({multiplo:.1f}× a média de {utils.fmt_brl(media_h)})")
        else:
            st.info("Nenhum gasto no mês atual para análise.")

        # Sankey: fluxo financeiro
        st.subheader("🌊 Fluxo Financeiro (Sankey)")
        mes_sankey = mes_atual
        df_ent_s = sh.get_entradas(mes_sankey)
        df_gas_s = sh.get_gastos(mes_sankey)

        if not df_ent_s.empty and not df_gas_s.empty:
            fontes_sankey = df_ent_s["fonte"].unique().tolist()
            cats_sankey = df_gas_s["categoria"].unique().tolist()
            nodes = fontes_sankey + ["Renda Total"] + cats_sankey
            ni = {n: i for i, n in enumerate(nodes)}

            sources, targets, values = [], [], []
            for fonte in fontes_sankey:
                val = df_ent_s[df_ent_s["fonte"] == fonte]["valor"].apply(safe_float).sum()
                sources.append(ni[fonte]); targets.append(ni["Renda Total"]); values.append(val)
            for cat in cats_sankey:
                val = df_gas_s[df_gas_s["categoria"] == cat]["valor_parcela"].apply(safe_float).sum()
                sources.append(ni["Renda Total"]); targets.append(ni[cat]); values.append(val)

            fig_sk = go.Figure(go.Sankey(
                node=dict(label=nodes, color=["#2ECC71"]*len(fontes_sankey) +
                          ["#F39C12"] + ["#E74C3C"]*len(cats_sankey)),
                link=dict(source=sources, target=targets, value=values)
            ))
            fig_sk.update_layout(title="Fluxo Financeiro do Mês", template="plotly_dark")
            st.plotly_chart(fig_sk, use_container_width=True)
