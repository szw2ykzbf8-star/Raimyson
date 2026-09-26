import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import io
from modules.auth import requer_permissao
from modules.google_sheets import ler_df

usuario = requer_permissao("relatorios")

st.title("📈 Relatórios e Análises")

# ── Helpers ───────────────────────────────────────────────────────────────────
def _safe_int(v):
    try:
        return int(float(v)) if str(v).strip() not in ("", "nan") else 0
    except Exception:
        return 0

def _safe_float(v, default=0.0):
    try:
        return float(v) if str(v).strip() not in ("", "nan") else default
    except Exception:
        return default

def _bool_col(series):
    return series.astype(str).str.lower().isin(["true", "1", "sim"])

def _to_excel(df: pd.DataFrame, sheet_name: str = "Dados") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buf.getvalue()

# ── Load data ─────────────────────────────────────────────────────────────────
df_hist         = ler_df("historico_precos")
df_produtos     = ler_df("produtos")
df_fornecedores = ler_df("fornecedores")
df_compras      = ler_df("compras")
df_itens_compra = ler_df("itens_compra")
df_pedidos      = ler_df("pedidos")
df_orcamentos   = ler_df("orcamentos")
df_unidades     = ler_df("unidades")
df_respostas    = ler_df("respostas")
df_cotacoes     = ler_df("cotacoes")
df_itens_rec    = ler_df("itens_recebimento")

if df_compras.empty:
    st.info("Ainda não há dados suficientes para gerar relatórios. Realize ao menos uma compra.")
    st.stop()

# ── Lookup maps ───────────────────────────────────────────────────────────────
prod_map = {}
if not df_produtos.empty:
    for _, r in df_produtos.iterrows():
        prod_map[_safe_int(r["id"])] = str(r.get("descricao", ""))

forn_map = {}
if not df_fornecedores.empty:
    for _, r in df_fornecedores.iterrows():
        forn_map[_safe_int(r["id"])] = str(r.get("razao_social", ""))

cot_nome_map = {}
if not df_cotacoes.empty:
    for _, r in df_cotacoes.iterrows():
        _nm = str(r.get("nome", "") or "").strip()
        cot_nome_map[_safe_int(r["id"])] = _nm if _nm else f"#{_safe_int(r['id'])}"

unid_nf = {}
if not df_unidades.empty:
    for _, r in df_unidades.iterrows():
        nm = str(r.get("nome", "") or "").strip()
        nf = str(r.get("nome_fantasia", "") or "").strip()
        if nm:
            unid_nf[nm] = nf if nf else nm

def _unid_label(u):
    return unid_nf.get(str(u or ""), str(u or "")) or str(u or "")

# ── Normalise compras ─────────────────────────────────────────────────────────
df_c = df_compras.copy()
df_c["id"]           = df_c["id"].apply(_safe_int)
df_c["valor_total"]  = df_c["valor_total"].apply(_safe_float)
df_c["fornecedor_id"] = df_c["fornecedor_id"].apply(_safe_int)
df_c["data_compra"]  = pd.to_datetime(df_c["data_compra"], errors="coerce")
df_c["unidade_label"] = df_c["unidade"].apply(lambda u: _unid_label(str(u or "")))
df_c["fornecedor"]   = df_c["fornecedor_id"].map(forn_map).fillna("Desconhecido")
_src = "status_recebimento"
if _src not in df_c.columns:
    df_c[_src] = "pendente"
df_c[_src] = df_c[_src].fillna("pendente").replace("", "pendente")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🗓️ Compras por Período",
    "📦 Produtos",
    "🏭 Fornecedores",
    "🏨 Hotéis",
    "📥 Recebimentos",
    "⬇️ Exportação",
])

# =============================================================================
# TAB 1 — COMPRAS POR PERÍODO
# =============================================================================
with tab1:
    st.subheader("Compras por Período")

    col1, col2, col3 = st.columns(3)
    with col1:
        data_ini = st.date_input("De", value=datetime.date.today().replace(day=1),
                                  format="DD/MM/YYYY", key="t1_ini")
    with col2:
        data_fim = st.date_input("Até", value=datetime.date.today(),
                                  format="DD/MM/YYYY", key="t1_fim")
    with col3:
        _unids = ["Todas"] + sorted(df_c["unidade_label"].dropna().unique().tolist())
        unid_sel = st.selectbox("Hotel / Unidade", _unids, key="t1_unid")

    cp = df_c[
        (df_c["data_compra"].dt.date >= data_ini) &
        (df_c["data_compra"].dt.date <= data_fim)
    ].copy()
    if unid_sel != "Todas":
        cp = cp[cp["unidade_label"] == unid_sel]

    if cp.empty:
        st.info("Nenhuma compra no período selecionado.")
    else:
        k1, k2, k3 = st.columns(3)
        k1.metric("Total gasto", f"R$ {cp['valor_total'].sum():,.2f}")
        k2.metric("Nº de compras", len(cp))
        k3.metric("Fornecedores", cp["fornecedor_id"].nunique())

        st.markdown("---")

        # Evolução temporal (semanal)
        cp2 = cp.copy()
        cp2["semana"] = cp2["data_compra"].dt.to_period("W").dt.start_time
        ev_temp = cp2.groupby("semana")["valor_total"].sum().reset_index()
        if len(ev_temp) > 1:
            fig_ev = px.area(ev_temp, x="semana", y="valor_total",
                             title="Evolução do Gasto (por semana)",
                             labels={"semana": "Semana", "valor_total": "R$"})
            fig_ev.update_traces(line_color="#2980B9", fillcolor="rgba(41,128,185,0.15)")
            st.plotly_chart(fig_ev, use_container_width=True)

        # Gasto por fornecedor
        por_forn = (cp.groupby("fornecedor")["valor_total"].sum()
                      .reset_index()
                      .sort_values("valor_total", ascending=False))
        fig_forn = px.bar(por_forn, x="fornecedor", y="valor_total",
                          title="Gasto por Fornecedor",
                          labels={"fornecedor": "Fornecedor", "valor_total": "R$"},
                          color="valor_total", color_continuous_scale="Blues")
        fig_forn.update_xaxes(tickangle=30)
        st.plotly_chart(fig_forn, use_container_width=True)

        st.dataframe(
            por_forn.rename(columns={"fornecedor": "Fornecedor", "valor_total": "R$ Total"})
                    .assign(**{"R$ Total": lambda d: d["R$ Total"].map("R$ {:,.2f}".format)}),
            hide_index=True, use_container_width=True,
        )

# =============================================================================
# TAB 2 — PRODUTOS
# =============================================================================
with tab2:
    sub_preco, sub_abc, sub_rank, sub_freq = st.tabs([
        "📈 Evolução de Preços",
        "🔺 Curva ABC",
        "💰 Ranking por Valor",
        "📆 Frequência de Compra",
    ])

    # ── Evolução de Preços ────────────────────────────────────────────────────
    with sub_preco:
        st.subheader("Evolução de Preço por Produto")
        if df_hist.empty or df_produtos.empty:
            st.info("Sem histórico de preços.")
        else:
            df_hn = df_hist.copy()
            df_hn["produto_id"]    = df_hn["produto_id"].apply(_safe_int)
            df_hn["fornecedor_id"] = df_hn["fornecedor_id"].apply(_safe_int)
            df_hn["ganhou"]        = _bool_col(df_hn["ganhou"])
            df_hn["data"]          = pd.to_datetime(df_hn["data"], errors="coerce")
            _pn = "preco_normalizado" if "preco_normalizado" in df_hn.columns else "preco"
            df_hn["pn"]            = df_hn[_pn].apply(_safe_float)

            busca_p = st.text_input("Buscar produto", placeholder="Digite parte do nome…", key="ep_busca")
            prods_at = df_produtos[_bool_col(df_produtos["ativo"])].copy() if not df_produtos.empty else pd.DataFrame()
            if busca_p and not prods_at.empty:
                prods_at = prods_at[prods_at["descricao"].str.contains(busca_p, case=False, na=False)]

            if prods_at.empty:
                st.info("Nenhum produto ativo encontrado." if not busca_p else "Nenhum resultado para a busca.")
            else:
                prod_sel_id = _safe_int(st.selectbox(
                    f"Produto ({len(prods_at)} encontrado(s))",
                    options=prods_at["id"].apply(_safe_int).tolist(),
                    format_func=lambda x: prod_map.get(x, f"#{x}"),
                    key="ep_prod",
                ))
                hist_p = df_hn[df_hn["produto_id"] == prod_sel_id].copy()
                hist_p["Fornecedor"] = hist_p["fornecedor_id"].map(forn_map).fillna("?")

                if hist_p.empty:
                    st.info("Sem histórico para este produto.")
                else:
                    fig_ep = px.line(hist_p, x="data", y="pn", color="Fornecedor",
                                     markers=True, title="Evolução do Preço Normalizado",
                                     labels={"data": "Data", "pn": "Preço (R$)"})
                    ganhadores = hist_p[hist_p["ganhou"]]
                    if not ganhadores.empty:
                        fig_ep.add_scatter(
                            x=ganhadores["data"], y=ganhadores["pn"],
                            mode="markers",
                            marker=dict(size=14, symbol="star", color="gold"),
                            name="⭐ Vencedor",
                        )
                    st.plotly_chart(fig_ep, use_container_width=True)

                    _var = hist_p.groupby("data")["pn"].min()
                    if len(_var) > 1:
                        delta_pct = (_var.iloc[-1] - _var.iloc[0]) / max(_var.iloc[0], 0.01) * 100
                        c1, c2 = st.columns(2)
                        c1.metric("Menor preço mais recente", f"R$ {_var.iloc[-1]:.2f}")
                        c2.metric("Variação total",
                                  f"{delta_pct:+.1f}%",
                                  delta="subiu" if delta_pct > 0 else "caiu",
                                  delta_color="inverse")

    # ── Curva ABC ─────────────────────────────────────────────────────────────
    with sub_abc:
        st.subheader("Curva ABC de Produtos")
        st.caption(
            "Classifica os produtos pelo valor total comprado: "
            "**A** = top 80% do gasto · **B** = 80–95% · **C** = 95–100%."
        )
        if df_itens_compra.empty:
            st.info("Sem itens de compra registrados.")
        else:
            df_ic = df_itens_compra.copy()
            df_ic["produto_id"] = df_ic["produto_id"].apply(_safe_int)
            df_ic["quantidade"] = df_ic["quantidade"].apply(_safe_float)
            _pni = "preco_norm" if "preco_norm" in df_ic.columns else "preco"
            df_ic["pn"]    = df_ic[_pni].apply(_safe_float)
            df_ic["valor"] = df_ic["quantidade"] * df_ic["pn"]

            abc = (df_ic.groupby("produto_id")["valor"].sum()
                        .reset_index()
                        .pipe(lambda d: d[d["valor"] > 0])
                        .sort_values("valor", ascending=False)
                        .reset_index(drop=True))
            abc["descricao"] = abc["produto_id"].map(prod_map).fillna("Desconhecido")
            abc["pct"]       = abc["valor"] / abc["valor"].sum() * 100
            abc["pct_acum"]  = abc["pct"].cumsum()
            abc["Classe"]    = abc["pct_acum"].apply(
                lambda x: "A" if x <= 80 else ("B" if x <= 95 else "C")
            )

            _cnt = abc["Classe"].value_counts()
            _val = abc.groupby("Classe")["valor"].sum()
            k1, k2, k3 = st.columns(3)
            k1.metric("Classe A", f"{_cnt.get('A', 0)} produtos", f"R$ {_val.get('A', 0):,.0f}")
            k2.metric("Classe B", f"{_cnt.get('B', 0)} produtos", f"R$ {_val.get('B', 0):,.0f}")
            k3.metric("Classe C", f"{_cnt.get('C', 0)} produtos", f"R$ {_val.get('C', 0):,.0f}")

            _cores = {"A": "#C0392B", "B": "#E67E22", "C": "#27AE60"}
            fig_abc = go.Figure()
            fig_abc.add_bar(
                x=abc["descricao"], y=abc["valor"],
                marker_color=[_cores.get(c, "#888") for c in abc["Classe"]],
                name="R$ Total",
                hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<br>Classe: "
                              + abc["Classe"].tolist()[0] + "<extra></extra>",
            )
            fig_abc.add_scatter(
                x=abc["descricao"], y=abc["pct_acum"],
                yaxis="y2", mode="lines", name="% Acumulado",
                line=dict(color="#2980B9", width=2),
                hovertemplate="%{y:.1f}%<extra></extra>",
            )
            fig_abc.update_layout(
                title="Curva ABC — Pareto de Produtos por Gasto",
                yaxis=dict(title="R$ Total"),
                yaxis2=dict(title="% Acumulado", overlaying="y", side="right",
                            range=[0, 105], ticksuffix="%"),
                xaxis_tickangle=45,
                showlegend=True,
                height=500,
            )
            st.plotly_chart(fig_abc, use_container_width=True)

            st.markdown(
                "<div style='display:flex;gap:20px;font-size:0.9em'>"
                "<span><b style='color:#C0392B'>■ A</b> — vitais (80% do gasto)</span>"
                "<span><b style='color:#E67E22'>■ B</b> — importantes (80–95%)</span>"
                "<span><b style='color:#27AE60'>■ C</b> — triviais (95–100%)</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            st.markdown("")

            classe_fil = st.selectbox("Filtrar por classe", ["Todas", "A", "B", "C"], key="abc_fil")
            df_abc_show = abc if classe_fil == "Todas" else abc[abc["Classe"] == classe_fil]
            st.dataframe(
                df_abc_show[["Classe", "descricao", "valor", "pct", "pct_acum"]].rename(columns={
                    "descricao": "Produto", "valor": "R$ Total",
                    "pct": "% do Total", "pct_acum": "% Acumulado",
                }).assign(**{
                    "R$ Total":    lambda d: d["R$ Total"].map("R$ {:,.2f}".format),
                    "% do Total":  lambda d: d["% do Total"].map("{:.2f}%".format),
                    "% Acumulado": lambda d: d["% Acumulado"].map("{:.2f}%".format),
                }),
                hide_index=True, use_container_width=True,
            )

    # ── Ranking por Valor ─────────────────────────────────────────────────────
    with sub_rank:
        st.subheader("Ranking de Produtos por Valor Comprado (R$)")
        if df_itens_compra.empty:
            st.info("Sem itens de compra registrados.")
        else:
            df_ic2 = df_itens_compra.copy()
            df_ic2["produto_id"] = df_ic2["produto_id"].apply(_safe_int)
            df_ic2["quantidade"] = df_ic2["quantidade"].apply(_safe_float)
            _pni2 = "preco_norm" if "preco_norm" in df_ic2.columns else "preco"
            df_ic2["pn"]    = df_ic2[_pni2].apply(_safe_float)
            df_ic2["valor"] = df_ic2["quantidade"] * df_ic2["pn"]

            rank = df_ic2.groupby("produto_id").agg(
                valor_total=("valor", "sum"),
                qtd_total=("quantidade", "sum"),
                n_compras=("produto_id", "count"),
            ).reset_index()
            rank["descricao"] = rank["produto_id"].map(prod_map).fillna("Desconhecido")
            rank = rank.sort_values("valor_total", ascending=False).reset_index(drop=True)

            top_n = st.slider("Exibir top N produtos", 10, 50, 20, key="rank_n")
            fig_rank = px.bar(
                rank.head(top_n), x="descricao", y="valor_total",
                title=f"Top {top_n} Produtos por Valor Total Comprado (R$)",
                labels={"descricao": "Produto", "valor_total": "R$ Total"},
                color="valor_total", color_continuous_scale="Reds",
            )
            fig_rank.update_xaxes(tickangle=45)
            st.plotly_chart(fig_rank, use_container_width=True)

            st.dataframe(
                rank.rename(columns={
                    "descricao": "Produto", "valor_total": "R$ Total",
                    "qtd_total": "Qtd Total", "n_compras": "Nº Compras",
                }).assign(**{"R$ Total": lambda d: d["R$ Total"].map("R$ {:,.2f}".format)}),
                hide_index=True, use_container_width=True,
            )

    # ── Frequência de Compra ──────────────────────────────────────────────────
    with sub_freq:
        st.subheader("Frequência de Compra por Produto")
        if df_itens_compra.empty or df_produtos.empty:
            st.info("Sem dados suficientes.")
        else:
            df_ic3 = df_itens_compra.copy()
            df_ic3["produto_id"] = df_ic3["produto_id"].apply(_safe_int)
            df_ic3["compra_id"]  = df_ic3["compra_id"].apply(_safe_int)
            df_ic3 = df_ic3.merge(
                df_c[["id", "data_compra"]].rename(columns={"id": "compra_id"}),
                on="compra_id", how="left"
            )

            freq = df_ic3.groupby("produto_id").agg(
                n_compras=("compra_id", "nunique"),
                ultima_compra=("data_compra", "max"),
                primeira_compra=("data_compra", "min"),
            ).reset_index()
            freq["descricao"] = freq["produto_id"].map(prod_map).fillna("Desconhecido")

            todos_pids    = set(df_produtos["id"].apply(_safe_int).tolist())
            comprados_pids = set(freq["produto_id"].tolist())
            nunca_pids    = todos_pids - comprados_pids
            nunca_desc    = sorted([prod_map.get(p, f"#{p}") for p in nunca_pids])

            c1, c2 = st.columns(2)
            c1.metric("Produtos já comprados", len(comprados_pids))
            c2.metric("Nunca comprados", len(nunca_pids))

            if nunca_desc:
                with st.expander(f"🔴 {len(nunca_pids)} produtos nunca comprados"):
                    for d in nunca_desc:
                        st.caption(f"• {d}")

            freq_s = freq.sort_values("n_compras", ascending=False)
            fig_freq = px.bar(
                freq_s.head(30), x="descricao", y="n_compras",
                title="Top 30 por Frequência de Compra",
                labels={"descricao": "Produto", "n_compras": "Nº de Compras"},
                color="n_compras", color_continuous_scale="Greens",
            )
            fig_freq.update_xaxes(tickangle=45)
            st.plotly_chart(fig_freq, use_container_width=True)

            # Produtos sem compra há mais de 60 dias
            _hoje = pd.Timestamp.today()
            freq["dias_sem_compra"] = (_hoje - freq["ultima_compra"]).dt.days
            antigos = freq[freq["dias_sem_compra"] > 60].sort_values("dias_sem_compra", ascending=False)
            if not antigos.empty:
                with st.expander(f"⚠️ {len(antigos)} produtos sem compra há mais de 60 dias"):
                    st.dataframe(
                        antigos[["descricao", "n_compras", "ultima_compra", "dias_sem_compra"]].rename(columns={
                            "descricao": "Produto", "n_compras": "Total Compras",
                            "ultima_compra": "Última Compra", "dias_sem_compra": "Dias sem compra",
                        }),
                        hide_index=True, use_container_width=True,
                    )

# =============================================================================
# TAB 3 — FORNECEDORES
# =============================================================================
with tab3:
    sub_desemp, sub_eco, sub_comp_forn = st.tabs([
        "🏆 Desempenho",
        "💡 Análise de Economia",
        "💲 Comparativo de Preços",
    ])

    with sub_desemp:
        st.subheader("Desempenho de Fornecedores")
        if df_hist.empty:
            st.info("Sem histórico de preços.")
        else:
            df_hd = df_hist.copy()
            df_hd["fornecedor_id"] = df_hd["fornecedor_id"].apply(_safe_int)
            df_hd["ganhou"]        = _bool_col(df_hd["ganhou"])
            _pnd = "preco_normalizado" if "preco_normalizado" in df_hd.columns else "preco"
            df_hd["pn"] = df_hd[_pnd].apply(_safe_float)

            vitorias   = df_hd[df_hd["ganhou"]].groupby("fornecedor_id").size().reset_index(name="vitorias")
            total_part = df_hd.groupby("fornecedor_id").size().reset_index(name="participacoes")
            preco_med  = df_hd.groupby("fornecedor_id")["pn"].mean().reset_index(name="preco_medio")

            desemp = (total_part
                      .merge(vitorias, on="fornecedor_id", how="left")
                      .fillna({"vitorias": 0})
                      .merge(preco_med, on="fornecedor_id", how="left"))
            desemp["vitorias"]     = desemp["vitorias"].astype(int)
            desemp["taxa_vitoria"] = (desemp["vitorias"] / desemp["participacoes"] * 100).round(1)
            desemp["Fornecedor"]   = desemp["fornecedor_id"].map(forn_map).fillna("Desconhecido")
            desemp = desemp.sort_values("taxa_vitoria", ascending=False)

            fig_d = px.bar(desemp, x="Fornecedor", y="taxa_vitoria",
                           title="Taxa de Vitória por Fornecedor (%)",
                           labels={"taxa_vitoria": "Taxa de Vitória (%)"},
                           color="taxa_vitoria", color_continuous_scale="RdYlGn")
            fig_d.update_xaxes(tickangle=30)
            st.plotly_chart(fig_d, use_container_width=True)

            st.dataframe(
                desemp[["Fornecedor", "participacoes", "vitorias", "taxa_vitoria", "preco_medio"]].rename(columns={
                    "participacoes": "Participações", "vitorias": "Vitórias",
                    "taxa_vitoria": "Taxa Vitória (%)", "preco_medio": "Preço Médio (R$)",
                }).assign(**{"Preço Médio (R$)": lambda d: d["Preço Médio (R$)"].map("R$ {:.2f}".format)}),
                hide_index=True, use_container_width=True,
            )

    with sub_eco:
        st.subheader("Análise de Economia por Cotação")
        st.caption(
            "Compara o preço vencedor com a média de todos os preços ofertados, "
            "estimando a economia gerada pelo processo de cotação."
        )
        if df_hist.empty:
            st.info("Sem histórico de preços.")
        else:
            df_he = df_hist.copy()
            df_he["cotacao_id"]    = df_he["cotacao_id"].apply(_safe_int)
            df_he["produto_id"]    = df_he["produto_id"].apply(_safe_int)
            df_he["ganhou"]        = _bool_col(df_he["ganhou"])
            _pne = "preco_normalizado" if "preco_normalizado" in df_he.columns else "preco"
            df_he["pn"] = df_he[_pne].apply(_safe_float)

            eco_rows = []
            for cot_id, grp in df_he.groupby("cotacao_id"):
                for pid, grp2 in grp.groupby("produto_id"):
                    if grp2.empty or len(grp2) < 2:
                        continue
                    media = grp2["pn"].mean()
                    ganhadores = grp2[grp2["ganhou"]]
                    if ganhadores.empty:
                        continue
                    melhor = ganhadores["pn"].min()
                    eco_pct = (media - melhor) / max(media, 0.01) * 100
                    eco_rows.append({
                        "cotacao_id":     cot_id,
                        "produto_id":     pid,
                        "media_precos":   media,
                        "preco_vencedor": melhor,
                        "economia_pct":   eco_pct,
                        "n_fornecedores": len(grp2),
                    })

            if not eco_rows:
                st.info("Sem dados suficientes (necessário ao menos 2 fornecedores por cotação).")
            else:
                df_eco = pd.DataFrame(eco_rows)
                df_eco["Cotação"] = df_eco["cotacao_id"].map(cot_nome_map).fillna(
                    df_eco["cotacao_id"].astype(str)
                )
                df_eco["Produto"] = df_eco["produto_id"].map(prod_map).fillna("?")

                eco_cot = (df_eco.groupby("Cotação")
                                 .agg(economia_media=("economia_pct", "mean"),
                                      n_produtos=("produto_id", "count"))
                                 .reset_index()
                                 .sort_values("economia_media", ascending=False))

                k1, k2 = st.columns(2)
                k1.metric("Economia média geral", f"{df_eco['economia_pct'].mean():.1f}%")
                k2.metric("Cotações analisadas", df_eco["cotacao_id"].nunique())

                fig_eco = px.bar(eco_cot, x="Cotação", y="economia_media",
                                 title="Economia por Cotação vs. Média dos Preços Ofertados",
                                 labels={"economia_media": "Economia Média (%)"},
                                 color="economia_media", color_continuous_scale="Greens")
                st.plotly_chart(fig_eco, use_container_width=True)

                with st.expander("Ver detalhe por produto"):
                    st.dataframe(
                        df_eco[["Cotação", "Produto", "n_fornecedores",
                                "media_precos", "preco_vencedor", "economia_pct"]].rename(columns={
                            "n_fornecedores": "Fornecedores",
                            "media_precos":   "Preço Médio (R$)",
                            "preco_vencedor": "Preço Vencedor (R$)",
                            "economia_pct":   "Economia %",
                        }).assign(**{
                            "Preço Médio (R$)":    lambda d: d["Preço Médio (R$)"].map("R$ {:.2f}".format),
                            "Preço Vencedor (R$)": lambda d: d["Preço Vencedor (R$)"].map("R$ {:.2f}".format),
                            "Economia %":          lambda d: d["Economia %"].map("{:.1f}%".format),
                        }),
                        hide_index=True, use_container_width=True,
                    )

    with sub_comp_forn:
        st.subheader("Comparativo de Preço por Fornecedor")
        st.caption(
            "Preço médio cotado de cada produto por fornecedor. "
            "Verde = mais barato, vermelho = mais caro na linha."
        )
        if df_hist.empty:
            st.info("Sem histórico de preços.")
        else:
            df_hcf = df_hist.copy()
            df_hcf["produto_id"]    = df_hcf["produto_id"].apply(_safe_int)
            df_hcf["fornecedor_id"] = df_hcf["fornecedor_id"].apply(_safe_int)
            _pncf = "preco_normalizado" if "preco_normalizado" in df_hcf.columns else "preco"
            df_hcf["pn"] = df_hcf[_pncf].apply(_safe_float)

            busca_cf = st.text_input(
                "Buscar produto (obrigatório — mínimo 2 caracteres)",
                placeholder="Ex: arroz, frango…", key="cf_busca"
            )
            if len(busca_cf.strip()) < 2:
                st.info("Digite ao menos 2 caracteres para filtrar os produtos.")
            else:
                prods_cf = df_produtos[
                    df_produtos["descricao"].str.contains(busca_cf.strip(), case=False, na=False)
                ] if not df_produtos.empty else pd.DataFrame()

                if prods_cf.empty:
                    st.info("Nenhum produto encontrado.")
                elif len(prods_cf) > 30:
                    st.warning(f"Muitos resultados ({len(prods_cf)}). Refine a busca para exibir a tabela.")
                else:
                    _pids_cf = prods_cf["id"].apply(_safe_int).tolist()
                    df_hcf_f = df_hcf[df_hcf["produto_id"].isin(_pids_cf)].copy()
                    if df_hcf_f.empty:
                        st.info("Sem cotações para esses produtos.")
                    else:
                        pivot = df_hcf_f.groupby(["produto_id", "fornecedor_id"])["pn"].mean().reset_index()
                        pivot["Produto"]    = pivot["produto_id"].map(prod_map).fillna("?")
                        pivot["Fornecedor"] = pivot["fornecedor_id"].map(forn_map).fillna("?")
                        pivot_t = pivot.pivot(index="Produto", columns="Fornecedor", values="pn")
                        st.dataframe(
                            pivot_t.style
                                   .format("R$ {:.2f}", na_rep="—")
                                   .background_gradient(axis=1, cmap="RdYlGn_r"),
                            use_container_width=True,
                        )

# =============================================================================
# TAB 4 — HOTÉIS
# =============================================================================
with tab4:
    sub_gasto_h, sub_orc = st.tabs([
        "📊 Gasto por Hotel",
        "🎯 Orçamento vs Gasto",
    ])

    with sub_gasto_h:
        st.subheader("Gasto por Hotel / Unidade")
        col_ini_h, col_fim_h = st.columns(2)
        with col_ini_h:
            ini_h = st.date_input("De", value=datetime.date.today().replace(day=1),
                                   format="DD/MM/YYYY", key="h_ini")
        with col_fim_h:
            fim_h = st.date_input("Até", value=datetime.date.today(),
                                   format="DD/MM/YYYY", key="h_fim")

        ch = df_c[
            (df_c["data_compra"].dt.date >= ini_h) &
            (df_c["data_compra"].dt.date <= fim_h)
        ].copy()

        if ch.empty:
            st.info("Nenhuma compra no período.")
        else:
            por_hotel = (ch.groupby("unidade_label")["valor_total"].sum()
                           .reset_index().sort_values("valor_total", ascending=False))
            fig_pie = px.pie(por_hotel, names="unidade_label", values="valor_total",
                             title="Distribuição do Gasto por Hotel",
                             color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig_pie, use_container_width=True)

            ch2 = ch.copy()
            ch2["mes"] = ch2["data_compra"].dt.to_period("M").dt.to_timestamp()
            ev_h = ch2.groupby(["mes", "unidade_label"])["valor_total"].sum().reset_index()
            if len(ev_h["mes"].unique()) > 1:
                fig_ev_h = px.line(ev_h, x="mes", y="valor_total", color="unidade_label",
                                   markers=True, title="Evolução Mensal por Hotel",
                                   labels={"mes": "Mês", "valor_total": "R$",
                                           "unidade_label": "Hotel"})
                st.plotly_chart(fig_ev_h, use_container_width=True)

            st.dataframe(
                por_hotel.rename(columns={"unidade_label": "Hotel", "valor_total": "R$ Total"})
                         .assign(**{"R$ Total": lambda d: d["R$ Total"].map("R$ {:,.2f}".format)}),
                hide_index=True, use_container_width=True,
            )

    with sub_orc:
        st.subheader("Orçamento vs Gasto por Unidade")
        if df_orcamentos.empty:
            st.info("Configure os orçamentos na página de Configurações.")
        else:
            hoje_orc = datetime.date.today()
            c1_orc, c2_orc = st.columns(2)
            with c1_orc:
                mes_sel = st.selectbox(
                    "Mês", range(1, 13), index=hoje_orc.month - 1, key="orc_mes",
                    format_func=lambda m: [
                        "Jan","Fev","Mar","Abr","Mai","Jun",
                        "Jul","Ago","Set","Out","Nov","Dez"
                    ][m - 1],
                )
            with c2_orc:
                ano_sel = st.number_input("Ano", value=hoje_orc.year,
                                          min_value=2020, max_value=2099, key="orc_ano")

            df_orc_m = df_orcamentos.copy()
            df_orc_m["mes"] = df_orc_m["mes"].apply(_safe_int)
            df_orc_m["ano"] = df_orc_m["ano"].apply(_safe_int)
            orc_mes = df_orc_m[(df_orc_m["mes"] == mes_sel) & (df_orc_m["ano"] == ano_sel)]

            cm = df_c[
                (df_c["data_compra"].dt.month == mes_sel) &
                (df_c["data_compra"].dt.year == ano_sel)
            ].copy()

            if orc_mes.empty:
                st.info("Nenhum orçamento cadastrado para este período.")
            else:
                dados_orc = []
                for _, orc in orc_mes.iterrows():
                    unid_orc = str(orc.get("unidade", "") or "")
                    cm_unid  = cm[cm["unidade"].astype(str) == unid_orc]
                    gasto    = _safe_float(cm_unid["valor_total"].sum())
                    orcado   = _safe_float(orc.get("valor", 0))
                    saldo    = orcado - gasto
                    dados_orc.append({
                        "Hotel":       _unid_label(unid_orc) or unid_orc,
                        "Orçamento":   orcado,
                        "Gasto":       gasto,
                        "Saldo":       saldo,
                        "% Utilizado": (gasto / orcado * 100) if orcado > 0 else 0.0,
                    })

                df_ov = pd.DataFrame(dados_orc)
                fig_orc = go.Figure()
                fig_orc.add_bar(x=df_ov["Hotel"], y=df_ov["Orçamento"],
                                name="Orçamento", marker_color="#2980B9")
                fig_orc.add_bar(x=df_ov["Hotel"], y=df_ov["Gasto"],
                                name="Gasto", marker_color="#E74C3C")
                fig_orc.update_layout(barmode="group", title="Orçamento vs Gasto por Hotel")
                st.plotly_chart(fig_orc, use_container_width=True)

                st.dataframe(
                    df_ov.assign(**{
                        "Orçamento":   lambda d: d["Orçamento"].map("R$ {:,.2f}".format),
                        "Gasto":       lambda d: d["Gasto"].map("R$ {:,.2f}".format),
                        "Saldo":       lambda d: d["Saldo"].map("R$ {:,.2f}".format),
                        "% Utilizado": lambda d: d["% Utilizado"].map("{:.1f}%".format),
                    }),
                    hide_index=True, use_container_width=True,
                )

# =============================================================================
# TAB 5 — RECEBIMENTOS
# =============================================================================
with tab5:
    st.subheader("Relatório de Recebimentos")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total de ordens", len(df_c))
    k2.metric("Recebidas",   len(df_c[df_c[_src] == "recebido"]))
    k3.metric("Divergentes", len(df_c[df_c[_src] == "divergente"]))
    k4.metric("Pendentes",   len(df_c[df_c[_src] == "pendente"]))

    status_counts = df_c[_src].value_counts().reset_index()
    status_counts.columns = ["Status", "Qtd"]
    fig_st = px.pie(
        status_counts, names="Status", values="Qtd",
        title="Status das Ordens de Compra",
        color="Status",
        color_discrete_map={"recebido": "#27AE60", "divergente": "#E67E22", "pendente": "#3498DB"},
    )
    st.plotly_chart(fig_st, use_container_width=True)

    # Divergências detalhadas
    if not df_itens_rec.empty:
        df_ir = df_itens_rec.copy()
        df_ir["compra_id"]    = df_ir["compra_id"].apply(_safe_int)
        df_ir["produto_id"]   = df_ir["produto_id"].apply(_safe_int)
        df_ir["qtd_pedida"]   = df_ir["qtd_pedida"].apply(_safe_float)
        df_ir["qtd_recebida"] = df_ir["qtd_recebida"].apply(_safe_float)
        df_ir["diferenca"]    = df_ir["qtd_recebida"] - df_ir["qtd_pedida"]

        diverg = df_ir[df_ir["diferenca"] != 0].copy()
        if not diverg.empty:
            diverg["Produto"] = diverg["produto_id"].map(prod_map).fillna("?")
            diverg2 = diverg.merge(
                df_c[["id", "fornecedor", "unidade_label", "data_compra"]]
                    .rename(columns={"id": "compra_id"}),
                on="compra_id", how="left",
            )
            with st.expander(f"⚠️ {len(diverg2)} divergência(s) de recebimento"):
                st.dataframe(
                    diverg2[["compra_id", "Produto", "fornecedor", "unidade_label",
                              "qtd_pedida", "qtd_recebida", "diferenca", "data_compra"]].rename(columns={
                        "compra_id": "Compra #", "fornecedor": "Fornecedor",
                        "unidade_label": "Hotel", "qtd_pedida": "Qtd Pedida",
                        "qtd_recebida": "Qtd Recebida", "diferenca": "Diferença",
                        "data_compra": "Data",
                    }),
                    hide_index=True, use_container_width=True,
                )

    # Ordens pendentes
    pendentes = df_c[df_c[_src] == "pendente"][
        ["id", "fornecedor", "unidade_label", "data_compra", "valor_total"]
    ].copy()
    if not pendentes.empty:
        pendentes["data_compra"] = pendentes["data_compra"].dt.date
        st.markdown("### 🕐 Ordens Pendentes de Recebimento")
        st.dataframe(
            pendentes.rename(columns={
                "id": "Compra #", "fornecedor": "Fornecedor",
                "unidade_label": "Hotel", "data_compra": "Data Compra",
                "valor_total": "Valor (R$)",
            }).assign(**{"Valor (R$)": lambda d: d["Valor (R$)"].map("R$ {:,.2f}".format)}),
            hide_index=True, use_container_width=True,
        )
    else:
        st.success("✅ Todas as ordens foram recebidas.")

# =============================================================================
# TAB 6 — EXPORTAÇÃO
# =============================================================================
with tab6:
    st.subheader("Exportar Dados para Excel")
    st.caption("Cada botão gera um arquivo `.xlsx` para download.")

    col_e1, col_e2 = st.columns(2)

    with col_e1:
        if not df_c.empty:
            _exp_c = df_c[["id", "fornecedor", "unidade_label", "data_compra",
                            "valor_total", _src]].copy()
            _exp_c.columns = ["ID", "Fornecedor", "Hotel", "Data", "Valor R$", "Status"]
            st.download_button(
                "⬇️ Compras",
                data=_to_excel(_exp_c, "Compras"),
                file_name=f"compras_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        if not df_hist.empty:
            _exp_h = df_hist.copy()
            _exp_h["Produto"]    = _exp_h["produto_id"].apply(_safe_int).map(prod_map)
            _exp_h["Fornecedor"] = _exp_h["fornecedor_id"].apply(_safe_int).map(forn_map)
            st.download_button(
                "⬇️ Histórico de Preços",
                data=_to_excel(_exp_h, "Histórico"),
                file_name=f"historico_precos_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        if not df_produtos.empty:
            st.download_button(
                "⬇️ Cadastro de Produtos",
                data=_to_excel(df_produtos, "Produtos"),
                file_name=f"produtos_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with col_e2:
        if not df_itens_compra.empty:
            _exp_ic = df_itens_compra.copy()
            _exp_ic["Produto"] = _exp_ic["produto_id"].apply(_safe_int).map(prod_map)
            st.download_button(
                "⬇️ Itens de Compra",
                data=_to_excel(_exp_ic, "Itens Compra"),
                file_name=f"itens_compra_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        if not df_fornecedores.empty:
            st.download_button(
                "⬇️ Cadastro de Fornecedores",
                data=_to_excel(df_fornecedores, "Fornecedores"),
                file_name=f"fornecedores_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        if not df_itens_rec.empty:
            _exp_rec = df_itens_rec.copy()
            _exp_rec["Produto"] = _exp_rec["produto_id"].apply(_safe_int).map(prod_map)
            st.download_button(
                "⬇️ Recebimentos",
                data=_to_excel(_exp_rec, "Recebimentos"),
                file_name=f"recebimentos_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
