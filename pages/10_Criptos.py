import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import date
from src import auth, sheets as sh, utils

auth.require_auth()

# Garante que a aba existe no Google Sheets (cria automaticamente se necessário)
sh.ensure_sheet("criptos", [
    "id", "moeda", "simbolo", "quantidade", "preco_compra_brl",
    "data_compra", "exchange", "conta_origem",
    "preco_venda_brl", "data_venda", "status", "criado_em",
])

st.title("₿ Criptomoedas")

# Moedas disponíveis no Nubank e mais comuns
MOEDAS = {
    "Bitcoin (BTC)":       ("bitcoin",       "BTC"),
    "Ethereum (ETH)":      ("ethereum",      "ETH"),
    "Solana (SOL)":        ("solana",        "SOL"),
    "Cardano (ADA)":       ("cardano",       "ADA"),
    "Polkadot (DOT)":      ("polkadot",      "DOT"),
    "Chainlink (LINK)":    ("chainlink",     "LINK"),
    "Uniswap (UNI)":       ("uniswap",       "UNI"),
    "Litecoin (LTC)":      ("litecoin",      "LTC"),
    "USDT (Tether)":       ("tether",        "USDT"),
    "USDC":                ("usd-coin",      "USDC"),
}

EXCHANGES = ["Nubank", "Binance", "Coinbase", "Mercado Bitcoin", "Bitso", "Outro"]


@st.cache_data(ttl=3600)
def buscar_cotacoes(ids: tuple) -> dict:
    """Busca cotações em BRL via CoinGecko. Cache de 1 hora."""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": ",".join(ids), "vs_currencies": "brl", "include_24hr_change": "true"}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


def _fetch_hist(coin_id: str, days: int) -> list:
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        r = requests.get(url, params={"vs_currency": "brl", "days": days}, timeout=10)
        r.raise_for_status()
        return r.json().get("prices", [])
    except Exception:
        return []

@st.cache_data(ttl=300)
def buscar_historico_1d(coin_id: str) -> list:
    return _fetch_hist(coin_id, 1)

@st.cache_data(ttl=1800)
def buscar_historico_7d(coin_id: str) -> list:
    return _fetch_hist(coin_id, 7)

@st.cache_data(ttl=3600)
def buscar_historico_30d(coin_id: str) -> list:
    return _fetch_hist(coin_id, 30)

@st.cache_data(ttl=86400)
def buscar_historico_365d(coin_id: str) -> list:
    return _fetch_hist(coin_id, 365)

_HIST_FUNCS = {
    1:   buscar_historico_1d,
    7:   buscar_historico_7d,
    30:  buscar_historico_30d,
    365: buscar_historico_365d,
}


tabs = st.tabs(["Portfólio", "Nova Compra", "Venda", "Histórico"])

# ─── Portfólio ────────────────────────────────────────────────────────────────

with tabs[0]:
    df = sh.get_criptos("ATIVO")

    if df.empty:
        st.info("Nenhuma criptomoeda cadastrada.")
    else:
        simbolos_para_id = {v[1]: v[0] for v in MOEDAS.values()}
        ids_necessarios = tuple(
            simbolos_para_id.get(row["simbolo"], row["simbolo"].lower())
            for _, row in df.iterrows()
            if row["simbolo"] in simbolos_para_id
        )

        cotacoes = buscar_cotacoes(ids_necessarios) if ids_necessarios else {}

        total_investido = df["preco_compra_brl"].astype(float).sum()
        total_atual = 0.0
        rows_portfolio = []

        for _, row in df.iterrows():
            qtd       = float(row["quantidade"])
            preco_med = float(row["preco_compra_brl"]) / qtd if qtd else 0
            cg_id     = simbolos_para_id.get(row["simbolo"], "")
            dados_cg  = cotacoes.get(cg_id, {})
            preco_atu = dados_cg.get("brl", None)
            var_24h   = dados_cg.get("brl_24h_change", None)
            val_atual = preco_atu * qtd if preco_atu else None
            lucro     = val_atual - float(row["preco_compra_brl"]) if val_atual is not None else None
            lucro_pct = (lucro / float(row["preco_compra_brl"]) * 100) if lucro is not None and float(row["preco_compra_brl"]) else None

            if val_atual is not None:
                total_atual += val_atual

            rows_portfolio.append({
                "id":        row["id"],
                "moeda":     row["moeda"],
                "simbolo":   row["simbolo"],
                "qtd":       qtd,
                "preco_med": preco_med,
                "investido": float(row["preco_compra_brl"]),
                "val_atual": val_atual,
                "lucro":     lucro,
                "lucro_pct": lucro_pct,
                "var_24h":   var_24h,
                "preco_atu": preco_atu,
                "exchange":  row.get("exchange", "—"),
                "data":      row["data_compra"],
            })

        # KPIs
        lucro_total = total_atual - total_investido if total_atual else None
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total Investido", utils.fmt_brl(total_investido))
        with c2:
            st.metric("Valor Atual Estimado",
                      utils.fmt_brl(total_atual) if total_atual else "Sem cotação")
        with c3:
            if lucro_total is not None:
                delta = f"{lucro_total/total_investido*100:.2f}%" if total_investido else "0%"
                st.metric("Lucro / Prejuízo", utils.fmt_brl(lucro_total), delta=delta)
            else:
                st.metric("Lucro / Prejuízo", "—")

        if not cotacoes:
            st.warning("Não foi possível buscar cotações. Valores atuais indisponíveis.")
        else:
            st.caption("Cotações via CoinGecko · atualização a cada 1 hora")

        st.markdown("---")

        for r in rows_portfolio:
            has_confirm = st.session_state.get(f"confirm_del_cr_{r['id']}", False)
            with st.expander(f"₿ {r['moeda']} ({r['simbolo']}) — {r['exchange']}", expanded=has_confirm):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("Quantidade", f"{r['qtd']:.8g} {r['simbolo']}")
                    st.metric("Preço médio pago", utils.fmt_brl(r["preco_med"]))
                with c2:
                    st.metric("Total investido", utils.fmt_brl(r["investido"]))
                    if r["preco_atu"]:
                        st.metric("Preço atual", utils.fmt_brl(r["preco_atu"]))
                    else:
                        st.metric("Preço atual", "—")
                with c3:
                    st.metric("Valor atual", utils.fmt_brl(r["val_atual"]) if r["val_atual"] else "—")
                    if r["lucro"] is not None:
                        st.metric("Lucro / Prejuízo", utils.fmt_brl(r["lucro"]),
                                  delta=f"{r['lucro_pct']:.2f}%")
                    else:
                        st.metric("Lucro / Prejuízo", "—")
                with c4:
                    if r["var_24h"] is not None:
                        st.metric("Variação 24h", f"{r['var_24h']:.2f}%",
                                  delta=f"{r['var_24h']:.2f}%")
                    st.metric("Comprado em", utils.fmt_data(r["data"]))

                # ── Gráfico histórico de preço ──────────────────────
                cg_id_chart = simbolos_para_id.get(r["simbolo"], "")
                if cg_id_chart:
                    st.markdown("---")
                    periodo_map = {"24h": 1, "7 dias": 7, "1 mês": 30, "1 ano": 365}
                    periodo_sel = st.radio(
                        "Período", list(periodo_map.keys()), horizontal=True,
                        key=f"periodo_{r['id']}"
                    )
                    days_sel = periodo_map[periodo_sel]
                    hist = _HIST_FUNCS[days_sel](cg_id_chart)
                    if hist:
                        df_h = pd.DataFrame(hist, columns=["ts", "preco"])
                        df_h["data"] = pd.to_datetime(df_h["ts"], unit="ms")
                        df_h["preco"] = df_h["preco"].astype(float)
                        p0 = df_h["preco"].iloc[0]
                        p1 = df_h["preco"].iloc[-1]
                        var = (p1 - p0) / p0 * 100 if p0 else 0
                        cor = "#2ECC71" if var >= 0 else "#E74C3C"
                        fill_cor = "rgba(46,204,113,0.15)" if var >= 0 else "rgba(231,76,60,0.15)"
                        fig_h = go.Figure()
                        fig_h.add_trace(go.Scatter(
                            x=df_h["data"], y=df_h["preco"],
                            fill="tozeroy", fillcolor=fill_cor,
                            line=dict(color=cor, width=2),
                            name="Preço BRL", hovertemplate="%{y:,.2f} BRL<extra></extra>"
                        ))
                        if r["preco_med"] > 0:
                            fig_h.add_hline(
                                y=r["preco_med"], line_dash="dot", line_color="#F39C12",
                                annotation_text=f"Seu preço: {utils.fmt_brl(r['preco_med'])}",
                                annotation_position="top right",
                                annotation=dict(font_color="#F39C12", font_size=11)
                            )
                        fig_h.update_layout(
                            title=dict(text=f"{r['simbolo']} · {var:+.2f}% ({periodo_sel})", font_size=14),
                            xaxis_title="", yaxis_title="BRL",
                            height=280, template="plotly_dark",
                            margin=dict(l=0, r=0, t=40, b=0),
                            showlegend=False,
                        )
                        st.plotly_chart(fig_h, use_container_width=True)
                    else:
                        st.caption("Histórico de preços indisponível no momento.")

                st.markdown("")
                if st.button("🗑️ Excluir posição", key=f"del_cr_{r['id']}"):
                    st.session_state[f"confirm_del_cr_{r['id']}"] = True

                if has_confirm:
                    pin = st.text_input("PIN de exclusão", type="password",
                                        max_chars=72, key=f"pin_cr_{r['id']}")
                    c_ok, c_cancel = st.columns(2)
                    with c_ok:
                        if st.button("Confirmar exclusão", key=f"ok_cr_{r['id']}"):
                            ok, msg = auth.verificar_pin_exclusao(pin)
                            if ok:
                                sh.delete_cripto(r["id"])
                                del st.session_state[f"confirm_del_cr_{r['id']}"]
                                st.success("Posição excluída.")
                                st.rerun()
                            else:
                                st.error(msg)
                    with c_cancel:
                        if st.button("Cancelar", key=f"cancel_cr_{r['id']}"):
                            del st.session_state[f"confirm_del_cr_{r['id']}"]
                            st.rerun()

# ─── Nova Compra ──────────────────────────────────────────────────────────────

with tabs[1]:
    contas_df = sh.get_contas()
    contas = contas_df["nome"].tolist() if not contas_df.empty else []

    moeda_sel = st.selectbox("Criptomoeda", list(MOEDAS.keys()), key="cripto_moeda")
    exchange_sel = st.selectbox("Exchange / Corretora", EXCHANGES, key="cripto_exchange")

    _k = st.session_state.get("_k_cripto", 0)
    with st.form(f"form_cripto_{_k}"):
        c1, c2 = st.columns(2)
        with c1:
            data_compra = st.date_input("Data da compra", value=date.today(), format="DD/MM/YYYY")
            quantidade  = st.number_input("Quantidade adquirida", min_value=0.0, value=None,
                                          step=0.00000001, format="%.8f", placeholder="0.00000000")
        with c2:
            valor_total = st.number_input("Valor total pago (R$)", min_value=0.01, value=None,
                                          step=0.01, format="%.2f", placeholder="0,00")
            conta_orig  = st.selectbox("Retirar de qual conta?",
                                       contas if contas else ["— nenhuma cadastrada —"])
        submitted = st.form_submit_button("Registrar Compra", use_container_width=True)

    if submitted:
        if quantidade is None or quantidade <= 0:
            st.warning("Informe a quantidade adquirida.")
        elif valor_total is None or valor_total <= 0:
            st.warning("Informe o valor total pago.")
        else:
            cg_id, simbolo = MOEDAS[moeda_sel]
            sh.add_cripto(moeda_sel, simbolo, quantidade, valor_total,
                          data_compra.isoformat(), exchange_sel, conta_orig)
            st.session_state["_k_cripto"] = _k + 1
            preco_unit = valor_total / quantidade
            st.success(f"Compra registrada! Preço médio: {utils.fmt_brl(preco_unit)}/{simbolo}")
            st.rerun()

# ─── Venda ────────────────────────────────────────────────────────────────────

with tabs[2]:
    df_ativos = sh.get_criptos("ATIVO")
    contas_df2 = sh.get_contas()
    contas2 = contas_df2["nome"].tolist() if not contas_df2.empty else []

    if df_ativos.empty:
        st.info("Nenhuma posição ativa para vender.")
    else:
        opcoes = [f"{row['moeda']} ({row['simbolo']})" for _, row in df_ativos.iterrows()]
        cripto_sel = st.selectbox("Selecione a posição", opcoes, key="venda_sel")
        idx = opcoes.index(cripto_sel)
        row_v = df_ativos.iloc[idx]

        qtd_v       = float(row_v["quantidade"])
        investido_v = float(row_v["preco_compra_brl"])
        preco_med_v = investido_v / qtd_v if qtd_v else 0

        st.info(f"**{qtd_v:.8g} {row_v['simbolo']}** · Preço médio: {utils.fmt_brl(preco_med_v)} · "
                f"Total investido: {utils.fmt_brl(investido_v)}")

        with st.form("form_venda_cripto"):
            c1, c2 = st.columns(2)
            with c1:
                data_venda  = st.date_input("Data da venda", value=date.today(), format="DD/MM/YYYY")
                valor_venda = st.number_input("Valor recebido (R$)", min_value=0.01, value=None,
                                              step=0.01, format="%.2f", placeholder="0,00")
            with c2:
                conta_dest  = st.selectbox("Depositar em qual conta?",
                                           contas2 if contas2 else ["— nenhuma cadastrada —"])
            submitted_v = st.form_submit_button("Registrar Venda", use_container_width=True)

        if submitted_v:
            if valor_venda is None or valor_venda <= 0:
                st.warning("Informe o valor recebido.")
            else:
                sh.vender_cripto(row_v["id"], valor_venda, data_venda.isoformat())
                sh.add_entrada(data_venda.isoformat(), valor_venda,
                               "Venda de Cripto", conta_dest,
                               f"Venda {row_v['moeda']}")
                lucro_v = valor_venda - investido_v
                msg = f"✅ Venda registrada! "
                msg += f"Lucro: {utils.fmt_brl(lucro_v)}" if lucro_v >= 0 else f"Prejuízo: {utils.fmt_brl(lucro_v)}"
                st.success(msg)
                st.rerun()

# ─── Histórico ────────────────────────────────────────────────────────────────

with tabs[3]:
    df_hist = sh.get_criptos("VENDIDO")
    if df_hist.empty:
        st.info("Nenhuma venda registrada.")
    else:
        total_inv_h = df_hist["preco_compra_brl"].astype(float).sum()
        total_ven_h = df_hist["preco_venda_brl"].astype(float).sum()
        lucro_h     = total_ven_h - total_inv_h
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total Investido", utils.fmt_brl(total_inv_h))
        with c2:
            st.metric("Total Recebido", utils.fmt_brl(total_ven_h))
        with c3:
            st.metric("Resultado Total", utils.fmt_brl(lucro_h),
                      delta=f"{lucro_h/total_inv_h*100:.2f}%" if total_inv_h else "0%")

        st.markdown("---")
        for _, row in df_hist.iterrows():
            inv = float(row["preco_compra_brl"])
            ven = float(row["preco_venda_brl"]) if row["preco_venda_brl"] else 0
            lucro = ven - inv
            st.write(
                f"**{row['moeda']}** · Compra: {utils.fmt_brl(inv)} → "
                f"Venda: {utils.fmt_brl(ven)} · "
                f"{'✅' if lucro >= 0 else '❌'} {utils.fmt_brl(lucro)} "
                f"({utils.fmt_data(row['data_compra'])} → {utils.fmt_data(row['data_venda'])})"
            )
