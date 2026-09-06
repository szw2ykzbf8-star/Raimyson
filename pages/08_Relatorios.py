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
        rows.append({"mes": m, "label": utils.formatar_mes(m),
                     "entradas": total_e, "gastos": total_g, "saldo": total_e - total_g})
    return pd.DataFrame(rows)


# ─── Fluxo Mensal ─────────────────────────────────────────────────────────────

with tabs[0]:
    n = st.slider("Últimos N meses", 3, 24, 12, key="sl_fluxo")
    df_m = build_monthly_data(n)

    # KPIs do período
    total_e_per = df_m["entradas"].sum()
    total_g_per = df_m["gastos"].sum()
    media_e = df_m["entradas"].mean()
    media_g = df_m["gastos"].mean()
    taxa_poup_per = ((total_e_per - total_g_per) / total_e_per * 100) if total_e_per > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Total Entradas (período)", utils.fmt_brl(total_e_per),
                  help=f"Média mensal: {utils.fmt_brl(media_e)}")
    with k2:
        st.metric("Total Gastos (período)", utils.fmt_brl(total_g_per),
                  help=f"Média mensal: {utils.fmt_brl(media_g)}")
    with k3:
        st.metric("Resultado (período)", utils.fmt_brl(total_e_per - total_g_per))
    with k4:
        st.metric("Taxa de Poupança", f"{taxa_poup_per:.1f}%",
                  help="(Total entradas − Total gastos) ÷ Total entradas × 100")

    st.markdown("")

    # Barras: entradas vs gastos
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(x=df_m["label"], y=df_m["entradas"],
                           name="Entradas", marker_color="#2ECC71"))
    fig1.add_trace(go.Bar(x=df_m["label"], y=df_m["gastos"],
                           name="Gastos", marker_color="#E74C3C"))
    fig1.update_layout(barmode="group", title="Entradas × Gastos por Mês",
                       template="plotly_dark", xaxis_title="Mês", yaxis_title="R$",
                       hovermode="x unified")
    st.plotly_chart(fig1, use_container_width=True)

    # Saldo mensal + acumulado
    df_m["saldo_acum"] = df_m["saldo"].cumsum()
    df_m["taxa_poup"] = df_m.apply(
        lambda r: (r["saldo"] / r["entradas"] * 100) if r["entradas"] > 0 else 0, axis=1)

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=df_m["label"], y=df_m["saldo"], name="Resultado do mês",
                           marker_color=["#2ECC71" if v >= 0 else "#E74C3C" for v in df_m["saldo"]]))
    fig2.add_trace(go.Scatter(x=df_m["label"], y=df_m["saldo_acum"],
                               name="Acumulado", mode="lines+markers",
                               line=dict(color="#F39C12", width=2), yaxis="y2"))
    fig2.update_layout(
        title="Resultado Mensal & Acumulado",
        template="plotly_dark",
        xaxis_title="Mês",
        yaxis=dict(title="Resultado (R$)"),
        yaxis2=dict(title="Acumulado (R$)", overlaying="y", side="right"),
        hovermode="x unified",
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Tabela resumo com taxa de poupança
    df_show = df_m[["label", "entradas", "gastos", "saldo", "taxa_poup"]].copy()
    df_show["entradas"] = df_show["entradas"].apply(utils.fmt_brl)
    df_show["gastos"] = df_show["gastos"].apply(utils.fmt_brl)
    df_show["saldo"] = df_show["saldo"].apply(utils.fmt_brl)
    df_show["taxa_poup"] = df_show["taxa_poup"].apply(lambda x: f"{x:.1f}%")
    df_show.columns = ["Mês", "Entradas", "Gastos", "Resultado", "Taxa de Poupança"]
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    # Top 10 maiores gastos individuais do período
    st.markdown("---")
    st.subheader("🔝 Maiores Gastos do Período")
    meses_per = df_m["mes"].tolist()
    todos_gas_per = pd.concat(
        [sh.get_gastos(m) for m in meses_per if not sh.get_gastos(m).empty],
        ignore_index=True
    ) if any(not sh.get_gastos(m).empty for m in meses_per) else pd.DataFrame()

    if not todos_gas_per.empty:
        todos_gas_per["valor_parcela"] = todos_gas_per["valor_parcela"].astype(float)
        top = todos_gas_per.nlargest(10, "valor_parcela")[
            ["data_compra", "descricao", "categoria", "forma_pagamento", "valor_parcela"]
        ].copy()
        top["data_compra"] = top["data_compra"].apply(utils.fmt_data)
        top["valor_parcela"] = top["valor_parcela"].apply(utils.fmt_brl)
        top["descricao"] = top["descricao"].fillna("—")
        top.columns = ["Data", "Descrição", "Categoria", "Pagamento", "Valor"]
        st.dataframe(top, use_container_width=True, hide_index=True)
    else:
        st.caption("Nenhum gasto no período.")


# ─── Categorias ───────────────────────────────────────────────────────────────

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
    ent_cat_mes = sh.get_entradas(mes_cat)
    total_renda = ent_cat_mes["valor"].apply(safe_float).sum() if not ent_cat_mes.empty else 0

    n_comp = st.slider("Comparar com últimos N meses", 1, 12, 3, key="sl_cat")
    meses_comp = utils.ultimos_meses(n_comp)

    if not df_cat_mes.empty:
        cat_group = df_cat_mes.groupby("categoria")["valor_parcela"].apply(
            lambda s: s.apply(safe_float).sum()).reset_index()
        cat_group.columns = ["Categoria", "Valor"]
        cat_group = cat_group.sort_values("Valor", ascending=False)
        if total_renda > 0:
            cat_group["% da Renda"] = (cat_group["Valor"] / total_renda * 100).round(1)

        col_a, col_b = st.columns(2)
        with col_a:
            fig_pizza = px.pie(cat_group, values="Valor", names="Categoria",
                               title=f"Distribuição por Categoria",
                               hole=0.4, template="plotly_dark")
            fig_pizza.update_traces(textinfo="label+percent", hovertemplate="%{label}: R$ %{value:,.2f}")
            st.plotly_chart(fig_pizza, use_container_width=True)

        with col_b:
            # Tabela com % da renda
            tbl = cat_group.copy()
            tbl["Valor"] = tbl["Valor"].apply(utils.fmt_brl)
            if "% da Renda" in tbl.columns:
                tbl["% da Renda"] = tbl["% da Renda"].apply(lambda x: f"{x:.1f}%")
            st.markdown(f"**Renda do mês: {utils.fmt_brl(total_renda)}**")
            st.dataframe(tbl, use_container_width=True, hide_index=True)

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

            df_comp_cat = cat_group[["Categoria", "Valor"]].merge(media_cat, on="Categoria", how="outer").fillna(0)
            fig_comp_cat = go.Figure()
            fig_comp_cat.add_trace(go.Bar(x=df_comp_cat["Categoria"], y=df_comp_cat["Valor"],
                                           name=utils.formatar_mes(mes_cat),
                                           marker_color="#E74C3C"))
            fig_comp_cat.add_trace(go.Bar(x=df_comp_cat["Categoria"], y=df_comp_cat["Média"],
                                           name=f"Média {n_comp} meses",
                                           marker_color="#3498DB"))
            fig_comp_cat.update_layout(barmode="group",
                                        title="Mês Atual × Média Histórica por Categoria",
                                        template="plotly_dark", hovermode="x unified")
            st.plotly_chart(fig_comp_cat, use_container_width=True)
    else:
        st.info("Nenhum gasto neste mês.")


# ─── Cartões ──────────────────────────────────────────────────────────────────

with tabs[2]:
    cartoes_df = sh.get_cartoes()
    todos_gastos = sh.get_gastos()

    if cartoes_df.empty or todos_gastos.empty:
        st.info("Nenhum dado disponível.")
    else:
        # Próximos 12 meses
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
            for mes_f in proximos_12:
                val = df_c[df_c["mes_referencia"] == mes_f]["valor_parcela"].apply(safe_float).sum()
                rows_comp.append({"Cartão": cartao, "Mês": utils.formatar_mes(mes_f), "Valor": val})

        df_faturas = pd.DataFrame(rows_comp)
        if not df_faturas.empty and df_faturas["Valor"].sum() > 0:
            fig_fat = px.bar(df_faturas, x="Mês", y="Valor", color="Cartão",
                             title="Faturas por Cartão — Próximos 12 Meses",
                             template="plotly_dark", barmode="stack",
                             hover_data={"Valor": ":.2f"})
            st.plotly_chart(fig_fat, use_container_width=True)

            # Tabela resumo por cartão
            resumo = df_faturas.groupby("Cartão")["Valor"].sum().reset_index()
            resumo["Valor"] = resumo["Valor"].apply(utils.fmt_brl)
            resumo.columns = ["Cartão", "Total Comprometido (12 meses)"]
            st.dataframe(resumo, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma parcela futura registrada.")

        # Gasto total por cartão (histórico)
        gastos_por_cartao = todos_gastos[todos_gastos["forma_pagamento"] == "Crédito"]
        if not gastos_por_cartao.empty:
            gc = gastos_por_cartao.groupby("conta_cartao")["valor_parcela"].apply(
                lambda s: s.apply(safe_float).sum()).reset_index()
            gc.columns = ["Cartão", "Total"]
            fig_gc = px.bar(gc, x="Cartão", y="Total",
                            text=gc["Total"].apply(utils.fmt_brl),
                            title="Total Gasto por Cartão (Histórico)",
                            template="plotly_dark", color="Cartão")
            fig_gc.update_traces(textposition="outside")
            st.plotly_chart(fig_gc, use_container_width=True)


# ─── Investimentos ─────────────────────────────────────────────────────────────

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

        total_aplic = df_inv_proc["Aplicado"].sum()
        total_atual = df_inv_proc["Atual"].sum()
        total_rend = df_inv_proc["Rendimento"].sum()

        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("Total Aplicado", utils.fmt_brl(total_aplic))
        with k2:
            st.metric("Valor Atual", utils.fmt_brl(total_atual),
                      delta=f"+{utils.fmt_brl(total_rend)}")
        with k3:
            rent_total = (total_rend / total_aplic * 100) if total_aplic > 0 else 0
            st.metric("Rentabilidade Total", f"{rent_total:.2f}%")

        col_a, col_b = st.columns(2)
        with col_a:
            fig_tipo = px.pie(df_inv_proc, values="Atual", names="Nome",
                              title="Composição do Portfólio (valor atual)",
                              hole=0.4, template="plotly_dark")
            st.plotly_chart(fig_tipo, use_container_width=True)
        with col_b:
            fig_rent = px.bar(df_inv_proc, x="Nome", y="Rent%", color="Tipo",
                              title="Rentabilidade por Investimento (%)",
                              text=df_inv_proc["Rent%"].apply(lambda x: f"{x:.2f}%"),
                              template="plotly_dark")
            fig_rent.update_traces(textposition="outside")
            st.plotly_chart(fig_rent, use_container_width=True)

        # Tabela detalhada
        tbl_inv = df_inv_proc.copy()
        tbl_inv["Aplicado"] = tbl_inv["Aplicado"].apply(utils.fmt_brl)
        tbl_inv["Atual"] = tbl_inv["Atual"].apply(utils.fmt_brl)
        tbl_inv["Rendimento"] = tbl_inv["Rendimento"].apply(utils.fmt_brl)
        tbl_inv["Rent%"] = tbl_inv["Rent%"].apply(lambda x: f"{x:.2f}%")
        st.dataframe(tbl_inv, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum investimento ativo.")

    if not df_inv_ret.empty:
        with st.expander("📋 Investimentos Encerrados"):
            for _, row in df_inv_ret.iterrows():
                if row["valor_retirado"]:
                    lucro = float(row["valor_retirado"]) - float(row["valor_aplicado"])
                    cor = "🟢" if lucro >= 0 else "🔴"
                    st.write(f"{cor} **{row['nome']}**: {utils.fmt_brl(float(row['valor_aplicado']))} → "
                             f"{utils.fmt_brl(float(row['valor_retirado']))} "
                             f"({'lucro' if lucro >= 0 else 'prejuízo'}: {utils.fmt_brl(abs(lucro))})")


# ─── Avançado ─────────────────────────────────────────────────────────────────

with tabs[4]:
    st.subheader("🔬 Análises Avançadas")
    n_adv = st.slider("Analisar últimos N meses", 3, 24, 6, key="sl_adv")
    df_adv = build_monthly_data(n_adv)

    # Patrimônio líquido
    st.subheader("💎 Patrimônio Líquido")
    contas_df_adv = sh.get_contas()
    todas_e = sh.get_entradas()
    todos_g = sh.get_gastos()
    todas_t = sh.get_transferencias()
    df_inv_adv = sh.get_investimentos("ATIVO")
    df_div_adv = sh.get_dividas()

    saldo_contas = sum(
        utils.calcular_saldo_conta(row["nome"], todas_e, todos_g, todas_t, contas_df_adv)
        for _, row in contas_df_adv.iterrows()
    ) if not contas_df_adv.empty else 0

    valor_invest = 0.0
    if not df_inv_adv.empty:
        hoje_adv = __import__("datetime").date.today().isoformat()
        for _, row in df_inv_adv.iterrows():
            res = utils.calcular_rendimento(
                float(row["valor_aplicado"]), row["taxa_tipo"],
                float(row["taxa_valor"]), row["data_aplicacao"], hoje_adv)
            valor_invest += res["valor_final"]

    total_dividas = 0.0
    if not df_div_adv.empty:
        for _, row in df_div_adv.iterrows():
            pagas = int(row["num_parcelas_pagas"])
            total = int(row["num_parcelas"])
            total_dividas += float(row["valor_parcela"]) * (total - pagas)

    patrimonio_liq = saldo_contas + valor_invest - total_dividas

    p1, p2, p3, p4 = st.columns(4)
    with p1:
        st.metric("💰 Saldo em Contas", utils.fmt_brl(saldo_contas))
    with p2:
        st.metric("📈 Investimentos", utils.fmt_brl(valor_invest))
    with p3:
        st.metric("🔴 Dívidas Restantes", utils.fmt_brl(total_dividas))
    with p4:
        st.metric("💎 Patrimônio Líquido", utils.fmt_brl(patrimonio_liq),
                  help="Saldo em Contas + Investimentos − Dívidas restantes")

    st.markdown("---")

    if len(df_adv) < 3:
        st.info("Acumule pelo menos 3 meses de dados para análises avançadas.")
    else:
        # Previsão simples por média móvel
        st.subheader("📊 Previsão de Gastos (Próximo Mês)")
        media_gastos = df_adv["gastos"].mean()
        std_gastos = df_adv["gastos"].std()
        tendencia = df_adv["gastos"].iloc[-1] - df_adv["gastos"].iloc[0]
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Previsão (média histórica)", utils.fmt_brl(media_gastos))
        with c2:
            st.metric("Intervalo provável",
                      f"{utils.fmt_brl(max(0, media_gastos - std_gastos))} – {utils.fmt_brl(media_gastos + std_gastos)}")
        with c3:
            st.metric("Tendência (período)", utils.fmt_brl(tendencia),
                      delta=f"{'↑ aumentando' if tendencia > 0 else '↓ reduzindo'}",
                      delta_color="inverse")

        # Heatmap
        st.markdown("---")
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
        if not df_heat.empty and df_heat.values.sum() > 0:
            fig_heat = px.imshow(df_heat.values,
                                  x=cats,
                                  y=[utils.formatar_mes(m) for m in meses_heat],
                                  color_continuous_scale="RdYlGn_r",
                                  title="Intensidade de Gasto por Categoria (R$)",
                                  aspect="auto",
                                  text_auto=".0f")
            fig_heat.update_layout(template="plotly_dark")
            st.plotly_chart(fig_heat, use_container_width=True)

        # Anomalias
        st.markdown("---")
        st.subheader("🚨 Detecção de Anomalias")
        mes_atual_adv = utils.mes_atual()
        df_atual = sh.get_gastos(mes_atual_adv)
        anomalias_encontradas = False
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
                    if media_h > 0 and val_atual > media_h * 1.5:
                        multiplo = val_atual / media_h
                        st.warning(f"⚠️ **{cat}**: {utils.fmt_brl(val_atual)} "
                                   f"({multiplo:.1f}× a média de {utils.fmt_brl(media_h)})")
                        anomalias_encontradas = True
        if not anomalias_encontradas:
            st.success("✅ Nenhuma anomalia detectada nos gastos do mês atual.")

        # Sankey
        st.markdown("---")
        st.subheader("🌊 Fluxo Financeiro (Sankey)")
        df_ent_s = sh.get_entradas(mes_atual_adv)
        df_gas_s = sh.get_gastos(mes_atual_adv)

        if not df_ent_s.empty and not df_gas_s.empty:
            fontes_sankey = df_ent_s["fonte"].unique().tolist()
            cats_sankey = df_gas_s["categoria"].unique().tolist()
            nodes = fontes_sankey + ["Renda Total"] + cats_sankey
            ni = {nd: i for i, nd in enumerate(nodes)}

            sources, targets, values = [], [], []
            for fonte in fontes_sankey:
                val = df_ent_s[df_ent_s["fonte"] == fonte]["valor"].apply(safe_float).sum()
                sources.append(ni[fonte]); targets.append(ni["Renda Total"]); values.append(val)
            for cat in cats_sankey:
                val = df_gas_s[df_gas_s["categoria"] == cat]["valor_parcela"].apply(safe_float).sum()
                sources.append(ni["Renda Total"]); targets.append(ni[cat]); values.append(val)

            fig_sk = go.Figure(go.Sankey(
                node=dict(label=nodes,
                          color=["#2ECC71"] * len(fontes_sankey) + ["#F39C12"] + ["#E74C3C"] * len(cats_sankey)),
                link=dict(source=sources, target=targets, value=values,
                          color="rgba(255,255,255,0.1)")
            ))
            fig_sk.update_layout(title=f"Fluxo Financeiro — {utils.formatar_mes(mes_atual_adv)}",
                                  template="plotly_dark")
            st.plotly_chart(fig_sk, use_container_width=True)
        else:
            st.info("Lance entradas e gastos no mês atual para ver o fluxo Sankey.")
