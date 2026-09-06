import streamlit as st
from datetime import date
from src import auth, sheets as sh, utils

auth.require_auth()

st.title("🏦 Contas Bancárias")

tabs = st.tabs(["Visão Geral", "Nova Conta", "Transferência"])

# ─── Visão Geral ──────────────────────────────────────────────────────────────

with tabs[0]:
    contas_df = sh.get_contas()
    if contas_df.empty:
        st.info("Nenhuma conta cadastrada.")
    else:
        todas_entradas  = sh.get_entradas()
        todos_gastos    = sh.get_gastos()
        todas_transf    = sh.get_transferencias()
        todos_invest_c  = sh.get_investimentos()
        todos_criptos_c = sh.get_criptos("ATIVO")
        todos_pgtos_c   = sh.get_pagamentos_contas()

        for _, row in contas_df.iterrows():
            bkd = utils.calcular_saldo_conta_breakdown(
                row["nome"], todas_entradas, todos_gastos, todas_transf, contas_df,
                todos_invest_c, todos_pgtos_c, todos_criptos_c
            )
            st.metric(
                label=f"🏦 {row['nome']} ({row['tipo']})",
                value=utils.fmt_brl(bkd["total"]),
                delta=f"Saldo inicial: {utils.fmt_brl(float(row['saldo_inicial']))}"
            )
            with st.expander("🔍 Detalhamento do saldo", expanded=False):
                d1, d2, d3 = st.columns(3)
                with d1:
                    st.metric("Saldo inicial", utils.fmt_brl(bkd["saldo_inicial"]))
                    st.metric("+ Entradas", utils.fmt_brl(bkd["entradas"]))
                    st.metric("+ Transf. recebidas", utils.fmt_brl(bkd["entradas_transf"]))
                with d2:
                    st.metric(f"− Gastos/Pix/Débito ({bkd['n_gastos']})", utils.fmt_brl(bkd["saidas_debito"]))
                    st.metric("− Transf. enviadas", utils.fmt_brl(bkd["saidas_transf"]))
                    st.metric("− Fat. cartão pagas", utils.fmt_brl(bkd["saidas_pgto"]))
                with d3:
                    st.metric("− Investimentos", utils.fmt_brl(bkd["saidas_invest"]))
                    st.metric("− Criptos", utils.fmt_brl(bkd["saidas_cripto"]))
                    st.metric("= Saldo calculado", utils.fmt_brl(bkd["total"]))

                conta_nome = row["nome"]
                st.markdown("---")

                # Entradas vinculadas
                if not todas_entradas.empty and "conta" in todas_entradas.columns:
                    df_e = todas_entradas[todas_entradas["conta"] == conta_nome]
                    if not df_e.empty:
                        st.markdown("**Entradas registradas nesta conta:**")
                        df_show_e = df_e[["data", "fonte", "valor", "descricao"]].copy()
                        df_show_e["valor"] = df_show_e["valor"].astype(float).apply(utils.fmt_brl)
                        df_show_e.columns = ["Data", "Fonte", "Valor", "Descrição"]
                        st.dataframe(df_show_e, use_container_width=True, hide_index=True)

                # Gastos vinculados
                if not todos_gastos.empty and "conta_cartao" in todos_gastos.columns:
                    mask_g = (todos_gastos["conta_cartao"] == conta_nome) & \
                             (todos_gastos["forma_pagamento"].isin(
                                 ["Pix", "Débito", "Débito (Cartão)", "Débito em Conta", "Dinheiro", "Boleto"]
                             ))
                    df_g = todos_gastos[mask_g]
                    if not df_g.empty:
                        st.markdown("**Gastos/Pix/Débito registrados nesta conta:**")
                        df_show_g = df_g[["data_compra", "descricao", "categoria", "forma_pagamento", "valor_parcela"]].copy()
                        df_show_g["valor_parcela"] = df_show_g["valor_parcela"].astype(float).apply(utils.fmt_brl)
                        df_show_g.columns = ["Data", "Descrição", "Categoria", "Forma Pgto", "Valor"]
                        st.dataframe(df_show_g, use_container_width=True, hide_index=True)

                # Investimentos vinculados
                if not todos_invest_c.empty and "conta_origem" in todos_invest_c.columns:
                    df_inv = todos_invest_c[
                        (todos_invest_c["conta_origem"] == conta_nome) &
                        (todos_invest_c["status"] == "ATIVO")
                    ]
                    if not df_inv.empty:
                        st.markdown("**Investimentos desta conta:**")
                        df_show_inv = df_inv[["nome", "tipo", "valor_aplicado", "data_aplicacao"]].copy()
                        df_show_inv["valor_aplicado"] = df_show_inv["valor_aplicado"].astype(float).apply(utils.fmt_brl)
                        df_show_inv.columns = ["Nome", "Tipo", "Valor", "Data"]
                        st.dataframe(df_show_inv, use_container_width=True, hide_index=True)

        st.markdown("---")

        # Extrato de transferências
        st.subheader("🔄 Transferências entre Contas")
        if not todas_transf.empty:
            df_show = todas_transf[["data", "conta_origem", "conta_destino", "valor", "descricao"]].copy()
            df_show["valor"] = df_show["valor"].astype(float).apply(utils.fmt_brl)
            df_show.columns = ["Data", "De", "Para", "Valor", "Descrição"]
            st.dataframe(df_show, use_container_width=True, hide_index=True)

            for _, row in todas_transf.iterrows():
                if st.button(f"🗑️ Excluir transferência {row['data']}", key=f"del_t_{row['id']}"):
                    st.session_state[f"confirm_del_t_{row['id']}"] = True
                if st.session_state.get(f"confirm_del_t_{row['id']}", False):
                    pin = st.text_input("PIN de exclusão", type="password",
                                        max_chars=72, key=f"pin_del_t_{row['id']}")
                    c_ok, c_cancel = st.columns(2)
                    with c_ok:
                        if st.button("Confirmar", key=f"ok_del_t_{row['id']}"):
                            ok, msg = auth.verificar_pin_exclusao(pin)
                            if ok:
                                sh.delete_transferencia(row["id"])
                                st.success("Transferência excluída.")
                                st.rerun()
                            else:
                                st.error(msg)
                    with c_cancel:
                        if st.button("Cancelar", key=f"cancel_del_t_{row['id']}"):
                            del st.session_state[f"confirm_del_t_{row['id']}"]
                            st.rerun()
        else:
            st.caption("Nenhuma transferência registrada.")

        # Excluir conta
        st.markdown("---")
        st.subheader("Excluir conta")
        conta_exc = st.selectbox("Conta", contas_df["nome"].tolist(), key="exc_conta")
        if st.button(f"🗑️ Excluir {conta_exc}"):
            st.session_state["confirm_del_conta"] = True

        if st.session_state.get("confirm_del_conta", False):
            pin = st.text_input("PIN de exclusão", type="password", max_chars=72)
            c_ok, c_cancel = st.columns(2)
            with c_ok:
                if st.button("Confirmar exclusão", key="ok_del_conta"):
                    ok, msg = auth.verificar_pin_exclusao(pin)
                    if ok:
                        row_exc = contas_df[contas_df["nome"] == conta_exc].iloc[0]
                        sh.delete_conta(row_exc["id"])
                        st.success("Conta excluída.")
                        st.rerun()
                    else:
                        st.error(msg)
            with c_cancel:
                if st.button("Cancelar", key="cancel_del_conta"):
                    st.session_state["confirm_del_conta"] = False
                    st.rerun()

# ─── Nova Conta ───────────────────────────────────────────────────────────────

with tabs[1]:
    _k = st.session_state.get("_k_conta", 0)
    with st.form(f"form_conta_{_k}"):
        nome = st.text_input("Nome da conta (ex: Sicredi, Mercado Pago)")
        tipo = st.selectbox("Tipo", ["Corrente", "Digital", "Poupança", "Outro"])
        saldo_inicial = st.number_input("Saldo inicial (R$)", min_value=0.0, value=None, step=0.01, format="%.2f", placeholder="0,00")
        submitted = st.form_submit_button("Salvar Conta", use_container_width=True)
    if submitted and nome:
        sh.add_conta(nome.strip(), tipo, saldo_inicial or 0.0)
        st.session_state["_k_conta"] = _k + 1
        st.success(f"Conta '{nome}' cadastrada!")
        st.rerun()

# ─── Transferência ────────────────────────────────────────────────────────────

with tabs[2]:
    contas_df = sh.get_contas()
    contas = contas_df["nome"].tolist() if not contas_df.empty else []

    if len(contas) < 2:
        st.info("Cadastre pelo menos 2 contas para fazer transferências.")
    else:
        with st.form("form_transf"):
            c1, c2 = st.columns(2)
            with c1:
                origem = st.selectbox("De", contas, key="transf_origem")
                valor = st.number_input("Valor (R$)", min_value=0.01, value=None, step=0.01, format="%.2f", placeholder="0,00")
            with c2:
                destino = st.selectbox("Para", [c for c in contas], key="transf_destino")
                data_t = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            descricao = st.text_input("Descrição (opcional)")
            submitted = st.form_submit_button("Transferir", use_container_width=True)

        if submitted:
            if valor is None or valor <= 0:
                st.warning("Informe o valor da transferência.")
            elif origem == destino:
                st.error("Conta de origem e destino devem ser diferentes.")
            else:
                sh.add_transferencia(data_t.isoformat(), valor, origem, destino, descricao)
                st.success(f"Transferência de {utils.fmt_brl(valor)} de {origem} para {destino} registrada!")
                st.rerun()
