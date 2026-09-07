import streamlit as st
from datetime import date, timedelta
from src import auth, sheets as sh, utils

auth.require_auth()

sh.ensure_sheet("viagens", sh._VIAGENS_HEADERS)
sh.ensure_sheet("gastos", [
    "id", "id_grupo", "data_compra", "data_fatura", "mes_referencia",
    "parcela_num", "total_parcelas", "valor_parcela", "valor_total",
    "categoria", "forma_pagamento", "conta_cartao", "descricao", "criado_em",
    "viagem_id",
])

st.title("✈️ Viagens")

df_viagens = sh.get_viagens()
viagem_ativa = sh.get_viagem_ativa()


def safe_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0


# ─── Viagem ativa ─────────────────────────────────────────────────────────────

if viagem_ativa:
    vid  = viagem_ativa["id"]
    nome = viagem_ativa.get("nome", "")
    dest = viagem_ativa.get("destino", "")
    d_ini = str(viagem_ativa.get("data_inicio", ""))
    d_fim = str(viagem_ativa.get("data_fim", ""))
    orc   = safe_float(viagem_ativa.get("orcamento", 0))

    df_g = sh.get_gastos_viagem(vid)
    total_gasto = df_g["valor_parcela"].apply(safe_float).sum() if not df_g.empty else 0.0
    saldo_viagem = orc - total_gasto
    pct = min(total_gasto / orc * 100, 100) if orc > 0 else 0

    dias_restantes = (date.fromisoformat(d_fim) - date.today()).days if d_fim else 0

    st.success(f"✈️ **Viagem ativa:** {nome} — {dest}")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Orçamento", utils.fmt_brl(orc))
    with c2:
        st.metric("Gasto até agora", utils.fmt_brl(total_gasto))
    with c3:
        st.metric("Saldo disponível", utils.fmt_brl(saldo_viagem),
                  delta=f"{-pct:.1f}% consumido", delta_color="inverse")
    with c4:
        st.metric("Dias restantes", max(dias_restantes, 0),
                  help=f"Viagem termina em {utils.fmt_data(d_fim)}")

    st.progress(pct / 100, text=f"{pct:.1f}% do orçamento utilizado")

    if not df_g.empty:
        st.subheader("💸 Gastos da viagem")
        cols_show = [c for c in ["data_compra", "descricao", "forma_pagamento", "conta_cartao", "valor_parcela"]
                     if c in df_g.columns]
        df_show = df_g[cols_show].copy()
        if "data_compra" in df_show.columns:
            df_show["data_compra"] = df_show["data_compra"].apply(utils.fmt_data)
        if "valor_parcela" in df_show.columns:
            df_show["valor_parcela"] = df_show["valor_parcela"].apply(safe_float).apply(utils.fmt_brl)
        df_show.columns = [c.replace("_", " ").title() for c in df_show.columns]
        st.dataframe(df_show, use_container_width=True, hide_index=True)
    else:
        st.caption("Nenhum gasto registrado ainda nesta viagem.")

    st.markdown("---")
    if st.button("🏁 Encerrar viagem", type="secondary"):
        sh.encerrar_viagem(vid)
        sh.invalidate("viagens")
        st.success(f"✅ Viagem **{nome}** encerrada! Total gasto: {utils.fmt_brl(total_gasto)} de {utils.fmt_brl(orc)}")
        st.rerun()

    st.markdown("---")

# ─── Nova viagem ─────────────────────────────────────────────────────────────

with st.expander("➕ Criar nova viagem", expanded=(viagem_ativa is None)):
    with st.form("form_viagem"):
        c1, c2 = st.columns(2)
        with c1:
            nome_v   = st.text_input("Nome da viagem", placeholder="ex: Buenos Aires")
            destino_v = st.text_input("Destino", placeholder="ex: Argentina")
        with c2:
            data_ini = st.date_input("Data de início", value=date.today())
            data_fim = st.date_input("Data de fim", value=date.today() + timedelta(days=7))
        orcamento_v = st.number_input(
            "Orçamento total (R$)", min_value=0.01, step=100.0,
            format="%.2f", placeholder="0,00", value=None
        )
        submitted = st.form_submit_button("Criar viagem", use_container_width=True, type="primary")

    if submitted:
        if not nome_v:
            st.warning("Informe o nome da viagem.")
        elif not destino_v:
            st.warning("Informe o destino.")
        elif data_fim < data_ini:
            st.warning("A data de fim deve ser posterior ao início.")
        elif not orcamento_v or orcamento_v <= 0:
            st.warning("Informe um orçamento maior que zero.")
        elif viagem_ativa:
            st.warning("Já existe uma viagem ativa. Encerre a atual antes de criar uma nova.")
        else:
            sh.criar_viagem(
                nome_v.strip(), destino_v.strip(),
                data_ini.isoformat(), data_fim.isoformat(),
                orcamento_v,
            )
            sh.invalidate("viagens")
            st.success(f"✈️ Viagem **{nome_v}** criada! Orçamento: {utils.fmt_brl(orcamento_v)}")
            st.rerun()

# ─── Histórico de viagens ─────────────────────────────────────────────────────

st.markdown("---")
st.subheader("📋 Histórico de viagens")

if df_viagens.empty:
    st.info("Nenhuma viagem cadastrada ainda.")
else:
    passadas = df_viagens[df_viagens["status"] == "encerrada"].copy() if "status" in df_viagens.columns else df_viagens.copy()

    if passadas.empty:
        st.caption("Nenhuma viagem encerrada ainda.")
    else:
        for _, v in passadas.sort_values("criado_em", ascending=False).iterrows():
            vid_h   = str(v["id"])
            nome_h  = str(v.get("nome", ""))
            dest_h  = str(v.get("destino", ""))
            d_ini_h = str(v.get("data_inicio", ""))
            d_fim_h = str(v.get("data_fim", ""))
            orc_h   = safe_float(v.get("orcamento", 0))

            df_gh = sh.get_gastos_viagem(vid_h)
            total_h = df_gh["valor_parcela"].apply(safe_float).sum() if not df_gh.empty else 0.0
            sobrou  = orc_h - total_h
            pct_h   = total_h / orc_h * 100 if orc_h > 0 else 0

            cor = "#2ECC71" if sobrou >= 0 else "#E74C3C"
            with st.expander(f"✈️ {nome_h} — {dest_h}  |  {utils.fmt_data(d_ini_h)} → {utils.fmt_data(d_fim_h)}"):
                h1, h2, h3 = st.columns(3)
                with h1:
                    st.metric("Orçamento", utils.fmt_brl(orc_h))
                with h2:
                    st.metric("Total gasto", utils.fmt_brl(total_h))
                with h3:
                    st.metric("Sobrou" if sobrou >= 0 else "Estourou",
                              utils.fmt_brl(abs(sobrou)),
                              delta=f"{pct_h:.1f}% do orçamento",
                              delta_color="normal" if sobrou >= 0 else "inverse")

                if not df_gh.empty:
                    # Mini DRE por tipo de gasto
                    st.markdown("**Distribuição por tipo de gasto:**")
                    if "descricao" in df_gh.columns and "valor_parcela" in df_gh.columns:
                        por_tipo = df_gh.groupby("forma_pagamento")["valor_parcela"].apply(
                            lambda x: x.apply(safe_float).sum()
                        ).reset_index()
                        por_tipo.columns = ["Forma", "Total"]
                        por_tipo["Total"] = por_tipo["Total"].apply(utils.fmt_brl)
                        st.dataframe(por_tipo, use_container_width=True, hide_index=True)
