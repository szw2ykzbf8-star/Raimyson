import streamlit as st
from datetime import date
from src import auth, sheets as sh, utils

st.set_page_config(page_title="Contas a Pagar — FinTrack", page_icon="📋", layout="wide")
auth.require_auth()

sh.ensure_sheet("pagamentos_contas", [
    "id", "tipo", "referencia_id", "nome", "mes_referencia",
    "valor", "conta_debito", "data_pagamento", "criado_em",
])

st.title("📋 Contas a Pagar")

# ── Navegação de mês ──────────────────────────────────────────────────────────

mes_hoje = utils.mes_atual()
col_prev, col_mes, col_next = st.columns([1, 3, 1])
with col_prev:
    if st.button("◀", key="cp_prev"):
        st.session_state["cp_mes"] = utils.mes_anterior(
            st.session_state.get("cp_mes", mes_hoje))
with col_next:
    if st.button("▶", key="cp_next"):
        st.session_state["cp_mes"] = utils.proximo_mes(
            st.session_state.get("cp_mes", mes_hoje))
mes_sel = st.session_state.get("cp_mes", mes_hoje)
with col_mes:
    st.markdown(f"<h4 style='text-align:center'>{utils.formatar_mes(mes_sel)}</h4>",
                unsafe_allow_html=True)

tabs = st.tabs(["📋 Contas do Mês", "🕒 Histórico"])

# ── Dados comuns ──────────────────────────────────────────────────────────────

contas_df    = sh.get_contas()
contas_lista = contas_df["nome"].tolist() if not contas_df.empty else []
pgtos_df     = sh.get_pagamentos_contas()
pgtos_mes    = pgtos_df[pgtos_df["mes_referencia"] == mes_sel] if not pgtos_df.empty else pgtos_df


def _pgto_existente(tipo: str, referencia_id: str) -> dict | None:
    if pgtos_mes.empty:
        return None
    mask = (pgtos_mes["tipo"] == tipo) & (pgtos_mes["referencia_id"] == referencia_id)
    rows = pgtos_mes[mask]
    return rows.iloc[0].to_dict() if not rows.empty else None


def _form_pagar(key_prefix: str, tipo: str, ref_id: str, nome: str,
                valor_sugerido: float, contas: list):
    """Exibe o formulário inline de pagamento. Retorna True se confirmado."""
    key_show = f"show_pay_{key_prefix}"
    if not st.session_state.get(key_show, False):
        if st.button("💰 Pagar", key=f"btn_pay_{key_prefix}", use_container_width=True):
            st.session_state[key_show] = True
            st.rerun()
        return

    with st.form(f"form_pay_{key_prefix}"):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            valor = st.number_input("Valor pago (R$)", value=float(valor_sugerido),
                                    min_value=0.01, step=0.01, format="%.2f")
        with col_b:
            conta_sel = st.selectbox("Conta debitada", contas if contas else ["—"])
        with col_c:
            data_pgto = st.date_input("Data do pagamento", value=date.today(), format="DD/MM/YYYY")
        col_ok, col_cancel = st.columns(2)
        with col_ok:
            ok = st.form_submit_button("✅ Confirmar", use_container_width=True)
        with col_cancel:
            cancel = st.form_submit_button("Cancelar", use_container_width=True)

    if ok:
        sh.add_pagamento_conta(tipo, ref_id, nome, mes_sel, valor, conta_sel, data_pgto.isoformat())
        st.session_state.pop(key_show, None)
        st.success(f"✅ {nome} registrado como pago!")
        st.rerun()
    if cancel:
        st.session_state.pop(key_show, None)
        st.rerun()


def _botao_estornar(pgto: dict, key_prefix: str):
    """Exibe o botão de estorno com confirmação por PIN."""
    key_show = f"show_est_{key_prefix}"
    if not st.session_state.get(key_show, False):
        if st.button("↩ Estornar", key=f"btn_est_{key_prefix}"):
            st.session_state[key_show] = True
            st.rerun()
        return

    pin = st.text_input("PIN de exclusão", type="password",
                        max_chars=72, key=f"pin_est_{key_prefix}")
    col_ok, col_cancel = st.columns(2)
    with col_ok:
        if st.button("Confirmar Estorno", key=f"ok_est_{key_prefix}"):
            ok, msg = auth.verificar_pin_exclusao(pin)
            if ok:
                sh.delete_pagamento_conta(pgto["id"])
                st.session_state.pop(key_show, None)
                st.success("Pagamento estornado.")
                st.rerun()
            else:
                st.error(msg)
    with col_cancel:
        if st.button("Cancelar", key=f"cancel_est_{key_prefix}"):
            st.session_state.pop(key_show, None)
            st.rerun()


# ─── Aba: Contas do Mês ───────────────────────────────────────────────────────

with tabs[0]:
    fixas_df   = sh.get_fixas()
    cartoes_df = sh.get_cartoes()
    todos_gastos = sh.get_gastos()

    # ── Contas Fixas ──────────────────────────────────────────────────────────

    st.subheader("🏠 Contas Fixas")

    fixas_mes = fixas_df[
        (fixas_df["ativo"] == "True") &
        (fixas_df["mes_inicio"] <= mes_sel) &
        ((fixas_df["mes_fim"] == "") | (fixas_df["mes_fim"] >= mes_sel))
    ] if not fixas_df.empty else fixas_df

    if fixas_mes.empty:
        st.info("Nenhuma conta fixa ativa neste mês.")
    else:
        total_fixas   = 0.0
        pagas_fixas   = 0.0
        for _, row in fixas_mes.iterrows():
            pgto = _pgto_existente("conta_fixa", row["id"])
            valor_ref = float(row["valor_referencia"])
            total_fixas += valor_ref
            if pgto:
                pagas_fixas += float(pgto["valor"])

        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("Total do mês", utils.fmt_brl(total_fixas))
        with k2:
            st.metric("Já pago", utils.fmt_brl(pagas_fixas))
        with k3:
            pendente = total_fixas - pagas_fixas
            st.metric("Pendente", utils.fmt_brl(pendente),
                      delta_color="inverse" if pendente > 0 else "normal")

        st.markdown("")

        for _, row in fixas_mes.iterrows():
            pgto = _pgto_existente("conta_fixa", row["id"])
            valor_ref = float(row["valor_referencia"])
            status = "✅ PAGA" if pgto else "⏳ PENDENTE"
            label  = f"{status} · **{row['nome']}** · {row['categoria']} · Vence dia {row['dia_vencimento']}"

            with st.expander(label, expanded=(pgto is None)):
                col_info, col_acao = st.columns([3, 1])
                with col_info:
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("Valor referência", utils.fmt_brl(valor_ref))
                    with c2:
                        st.metric("Categoria", row["categoria"])
                    with c3:
                        st.metric("Forma de pagamento", row["forma_pagamento"])
                    if pgto:
                        st.success(
                            f"Pago em {utils.fmt_data(pgto['data_pagamento'])} · "
                            f"{utils.fmt_brl(float(pgto['valor']))} · Conta: {pgto['conta_debito']}"
                        )
                with col_acao:
                    if pgto:
                        _botao_estornar(pgto, f"fixa_{row['id']}")
                    else:
                        _form_pagar(
                            f"fixa_{row['id']}", "conta_fixa", row["id"],
                            row["nome"], valor_ref, contas_lista
                        )

    # ── Faturas de Cartão ─────────────────────────────────────────────────────

    st.markdown("---")
    st.subheader("💳 Faturas de Cartão")

    if cartoes_df.empty:
        st.info("Nenhum cartão cadastrado.")
    else:
        total_faturas  = 0.0
        pagas_faturas  = 0.0

        for _, cartao in cartoes_df.iterrows():
            mask_fat = (
                (todos_gastos["conta_cartao"] == cartao["nome"]) &
                (todos_gastos["mes_referencia"] == mes_sel) &
                (todos_gastos["forma_pagamento"] == "Crédito")
            ) if not todos_gastos.empty else None

            valor_fatura = todos_gastos[mask_fat]["valor_parcela"].astype(float).sum() \
                if mask_fat is not None else 0.0

            pgto = _pgto_existente("fatura_cartao", cartao["id"])
            total_faturas += valor_fatura
            if pgto:
                pagas_faturas += float(pgto["valor"])

        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("Total faturas do mês", utils.fmt_brl(total_faturas))
        with k2:
            st.metric("Já pago", utils.fmt_brl(pagas_faturas))
        with k3:
            pendente_fat = total_faturas - pagas_faturas
            st.metric("Pendente", utils.fmt_brl(pendente_fat),
                      delta_color="inverse" if pendente_fat > 0 else "normal")

        st.markdown("")

        for _, cartao in cartoes_df.iterrows():
            mask_fat = (
                (todos_gastos["conta_cartao"] == cartao["nome"]) &
                (todos_gastos["mes_referencia"] == mes_sel) &
                (todos_gastos["forma_pagamento"] == "Crédito")
            ) if not todos_gastos.empty else None

            valor_fatura = todos_gastos[mask_fat]["valor_parcela"].astype(float).sum() \
                if mask_fat is not None else 0.0

            pgto  = _pgto_existente("fatura_cartao", cartao["id"])
            status = "✅ PAGA" if pgto else ("⏳ PENDENTE" if valor_fatura > 0 else "— Sem lançamentos")
            label  = (f"{status} · **{cartao['nome']}** · "
                      f"Fatura: {utils.fmt_brl(valor_fatura)} · "
                      f"Vence dia {cartao['dia_vencimento']}")

            with st.expander(label, expanded=(pgto is None and valor_fatura > 0)):
                col_info, col_acao = st.columns([3, 1])
                with col_info:
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("Valor da fatura", utils.fmt_brl(valor_fatura))
                    with c2:
                        st.metric("Fecha dia", cartao["dia_fechamento"])
                    with c3:
                        st.metric("Vence dia", cartao["dia_vencimento"])

                    # Detalhamento da fatura
                    if mask_fat is not None and valor_fatura > 0:
                        df_det = todos_gastos[mask_fat][
                            ["data_compra", "descricao", "categoria", "parcela_num",
                             "total_parcelas", "valor_parcela"]
                        ].copy()
                        df_det["data_compra"]   = df_det["data_compra"].apply(utils.fmt_data)
                        df_det["valor_parcela"] = df_det["valor_parcela"].astype(float).apply(utils.fmt_brl)
                        df_det["Parcela"]       = df_det.apply(
                            lambda r: f"{r['parcela_num']}/{r['total_parcelas']}", axis=1)
                        df_det = df_det[["data_compra", "descricao", "categoria", "Parcela", "valor_parcela"]]
                        df_det.columns = ["Data", "Descrição", "Categoria", "Parcela", "Valor"]
                        st.dataframe(df_det, use_container_width=True, hide_index=True)

                    if pgto:
                        st.success(
                            f"Pago em {utils.fmt_data(pgto['data_pagamento'])} · "
                            f"{utils.fmt_brl(float(pgto['valor']))} · Conta: {pgto['conta_debito']}"
                        )

                with col_acao:
                    if pgto:
                        _botao_estornar(pgto, f"cartao_{cartao['id']}")
                    elif valor_fatura > 0:
                        _form_pagar(
                            f"cartao_{cartao['id']}", "fatura_cartao", cartao["id"],
                            f"Fatura {cartao['nome']}", valor_fatura, contas_lista
                        )
                    else:
                        st.caption("Sem lançamentos neste mês.")


# ─── Aba: Histórico ───────────────────────────────────────────────────────────

with tabs[1]:
    if pgtos_df.empty:
        st.info("Nenhum pagamento registrado ainda.")
    else:
        n_meses_hist = st.slider("Últimos N meses", 1, 12, 3, key="hist_n")
        meses_hist   = utils.ultimos_meses(n_meses_hist)
        df_hist      = pgtos_df[pgtos_df["mes_referencia"].isin(meses_hist)].copy()

        if df_hist.empty:
            st.info("Nenhum pagamento no período selecionado.")
        else:
            df_hist = df_hist.sort_values("data_pagamento", ascending=False)

            total_hist = df_hist["valor"].astype(float).sum()
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Total pago no período", utils.fmt_brl(total_hist))
            with c2:
                st.metric("Número de pagamentos", str(len(df_hist)))

            st.markdown("---")

            for _, pgto in df_hist.iterrows():
                tipo_label = "🏠 Conta Fixa" if pgto["tipo"] == "conta_fixa" else "💳 Fatura Cartão"
                with st.expander(
                    f"{tipo_label} · **{pgto['nome']}** · "
                    f"{utils.formatar_mes(pgto['mes_referencia'])} · "
                    f"{utils.fmt_brl(float(pgto['valor']))}",
                    expanded=False,
                ):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("Valor pago", utils.fmt_brl(float(pgto["valor"])))
                    with c2:
                        st.metric("Conta debitada", pgto["conta_debito"])
                    with c3:
                        st.metric("Data do pagamento", utils.fmt_data(pgto["data_pagamento"]))

                    _botao_estornar(pgto.to_dict(), f"hist_{pgto['id']}")
