import streamlit as st
from datetime import date
from src import auth, sheets as sh, utils

auth.require_auth()

st.title("🔴 Dívidas")

tabs = st.tabs(["Acompanhamento", "Nova Dívida", "Simulador de Antecipação"])

# ─── Acompanhamento ───────────────────────────────────────────────────────────

with tabs[0]:
    df = sh.get_dividas()
    if df.empty:
        st.info("Nenhuma dívida cadastrada.")
    else:
        for _, row in df.iterrows():
            total_pagas = int(row["num_parcelas_pagas"])
            total_parcelas = int(row["num_parcelas"])
            restantes = total_parcelas - total_pagas
            valor_parcela = float(row["valor_parcela"])
            valor_original = float(row["valor_original"])
            pago = sum(
                float(p["valor_pago"])
                for _, p in sh.get_pgtos_divida(row["id"]).iterrows()
            ) if not sh.get_pgtos_divida(row["id"]).empty else total_pagas * valor_parcela

            restante_estimado = valor_parcela * restantes
            progresso = total_pagas / total_parcelas if total_parcelas > 0 else 0

            st.subheader(f"🔴 {row['nome']}")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Valor original", utils.fmt_brl(valor_original))
            with c2:
                st.metric("Parcela mensal", utils.fmt_brl(valor_parcela))
            with c3:
                st.metric("Parcelas pagas", f"{total_pagas}/{total_parcelas}")
            with c4:
                st.metric("Saldo devedor aprox.", utils.fmt_brl(restante_estimado))

            st.progress(progresso, text=f"{int(progresso*100)}% quitado")

            # Registrar pagamento
            with st.expander(f"💳 Registrar Pagamento — {row['nome']}"):
                with st.form(f"form_pgto_{row['id']}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        data_p = st.date_input("Data do pagamento", value=date.today(),
                                               format="DD/MM/YYYY", key=f"dp_{row['id']}")
                        is_antecip = st.checkbox("Pagamento antecipado?", key=f"ant_{row['id']}")
                    with c2:
                        valor_pago = st.number_input(
                            "Valor pago (R$)", value=valor_parcela,
                            min_value=0.01, step=0.01, format="%.2f",
                            key=f"vp_{row['id']}"
                        )
                        num_antecip = 1
                        economia = 0.0
                        if is_antecip:
                            num_antecip = st.number_input(
                                "Quantas parcelas antecipadas?", min_value=1,
                                max_value=restantes, value=1, key=f"na_{row['id']}"
                            )
                            economia = (valor_parcela * num_antecip) - valor_pago
                    desc_p = st.text_input("Descrição", key=f"desc_p_{row['id']}")
                    pagar = st.form_submit_button("Registrar Pagamento", use_container_width=True)

                if pagar:
                    sh.registrar_pagamento_divida(
                        row["id"], valor_pago, data_p.isoformat(),
                        bool(is_antecip), int(num_antecip), max(0, economia), desc_p
                    )
                    # Registra como gasto
                    sh.add_gasto(
                        data_p.isoformat(), data_p.isoformat(),
                        utils.mes_str(data_p.year, data_p.month),
                        1, 1, valor_pago, valor_pago, "Dívidas",
                        row["forma_pagamento"], row["conta_cartao"],
                        f"Pagamento {row['nome']}"
                    )
                    if is_antecip and economia > 0:
                        st.success(f"✅ Pagamento registrado! Economia de {utils.fmt_brl(economia)} em juros.")
                    else:
                        st.success("✅ Pagamento registrado!")
                    st.rerun()

            # Histórico de pagamentos
            pgtos = sh.get_pgtos_divida(row["id"])
            if not pgtos.empty:
                with st.expander("📋 Histórico de pagamentos"):
                    for _, p in pgtos.iterrows():
                        antecip_str = f" (antecipação de {p['num_antecipadas']}x)" \
                            if p["is_antecipacao"] == "True" else ""
                        economia_str = f" | Economia: {utils.fmt_brl(float(p['economia']))}" \
                            if float(p.get("economia", 0) or 0) > 0 else ""
                        st.write(f"• {utils.fmt_data(p['data'])} — {utils.fmt_brl(float(p['valor_pago']))}"
                                 f"{antecip_str}{economia_str}")

            # Excluir dívida
            if st.button(f"🗑️ Excluir dívida {row['nome']}", key=f"del_d_{row['id']}"):
                st.session_state[f"confirm_del_d_{row['id']}"] = True

            if st.session_state.get(f"confirm_del_d_{row['id']}", False):
                pin = st.text_input("PIN de exclusão", type="password",
                                    max_chars=72, key=f"pin_del_d_{row['id']}")
                c_ok, c_cancel = st.columns(2)
                with c_ok:
                    if st.button("Confirmar", key=f"ok_del_d_{row['id']}"):
                        ok, msg = auth.verificar_pin_exclusao(pin)
                        if ok:
                            sh.delete_divida(row["id"])
                            st.success("Dívida excluída.")
                            st.rerun()
                        else:
                            st.error(msg)
                with c_cancel:
                    if st.button("Cancelar", key=f"cancel_del_d_{row['id']}"):
                        del st.session_state[f"confirm_del_d_{row['id']}"]
                        st.rerun()

            st.markdown("---")

# ─── Nova Dívida ──────────────────────────────────────────────────────────────

with tabs[1]:
    contas_df = sh.get_contas()
    cartoes_df = sh.get_cartoes()
    contas = contas_df["nome"].tolist() if not contas_df.empty else []
    cartoes = cartoes_df["nome"].tolist() if not cartoes_df.empty else []

    forma = st.selectbox("Forma de pagamento",
                         ["Pix", "Débito em Conta", "Débito (Cartão)", "Boleto", "Crédito"])

    _k = st.session_state.get("_k_divida", 0)
    with st.form(f"form_divida_{_k}"):
        c1, c2 = st.columns(2)
        with c1:
            nome_d = st.text_input("Nome da dívida (ex: Dívida Nubank)")
            valor_orig = st.number_input("Valor original total (R$)", min_value=0.01, value=None, step=0.01, format="%.2f", placeholder="0,00")
            num_parc = st.number_input("Número total de parcelas", min_value=1, step=1, value=12)
            data_ini = st.date_input("Data de início", value=date.today(), format="DD/MM/YYYY")
        with c2:
            valor_parc = st.number_input("Valor da parcela (R$)", min_value=0.01, value=None, step=0.01, format="%.2f", placeholder="0,00")
            if forma == "Crédito":
                cc = st.selectbox("Cartão", cartoes if cartoes else ["— nenhum cadastrado —"])
            else:
                cc = st.selectbox("Conta", contas if contas else ["— nenhuma cadastrada —"])
        submitted = st.form_submit_button("Salvar Dívida", use_container_width=True)

    if submitted and nome_d:
        if valor_orig is None or valor_orig <= 0:
            st.warning("Informe o valor original da dívida.")
        elif valor_parc is None or valor_parc <= 0:
            st.warning("Informe o valor da parcela.")
        else:
            sh.add_divida(nome_d.strip(), valor_orig, valor_parc, int(num_parc),
                          data_ini.isoformat(), forma, cc, "")
            st.session_state["_k_divida"] = _k + 1
            st.success(f"Dívida '{nome_d}' cadastrada!")
            st.rerun()

# ─── Simulador de Antecipação ─────────────────────────────────────────────────

with tabs[2]:
    st.subheader("📊 Simulador de Antecipação")
    st.caption("Calcule quanto economiza pagando parcelas adiantado.")

    df_d = sh.get_dividas()
    if df_d.empty:
        st.info("Nenhuma dívida cadastrada.")
    else:
        opcoes = df_d["nome"].tolist()
        divida_sel = st.selectbox("Selecione a dívida", opcoes)
        row_d = df_d[df_d["nome"] == divida_sel].iloc[0]
        pagas = int(row_d["num_parcelas_pagas"])
        total = int(row_d["num_parcelas"])
        restantes_d = total - pagas
        val_parc = float(row_d["valor_parcela"])

        st.info(f"**Parcelas restantes:** {restantes_d} × {utils.fmt_brl(val_parc)} = "
                f"{utils.fmt_brl(restantes_d * val_parc)}")

        c1, c2 = st.columns(2)
        with c1:
            num_antecipar = st.slider("Quantas parcelas antecipar?", 1, max(1, restantes_d), 1)
        with c2:
            desconto_pct = st.number_input("Desconto oferecido (%)", min_value=0.0,
                                            max_value=100.0, step=0.1, format="%.1f")

        resultado = utils.simular_antecipacao(val_parc, num_antecipar, desconto_pct)

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("Valor sem desconto", utils.fmt_brl(resultado["valor_sem_desconto"]))
        with col_b:
            st.metric("Valor com desconto", utils.fmt_brl(resultado["valor_com_desconto"]))
        with col_c:
            st.metric("Economia em juros", utils.fmt_brl(resultado["economia"]),
                      delta=f"-{desconto_pct:.1f}%")

        if restantes_d - num_antecipar > 0:
            sobram = restantes_d - num_antecipar
            st.success(f"Após a antecipação, restarão **{sobram} parcelas** "
                       f"de {utils.fmt_brl(val_parc)} = {utils.fmt_brl(sobram * val_parc)}")
        else:
            st.success("🎉 Isso quitaria a dívida completamente!")
