import streamlit as st
from datetime import date
from src import auth, sheets as sh, utils

st.set_page_config(page_title="Contas — FinTrack", page_icon="🏦", layout="wide")
auth.require_auth()

st.title("🏦 Contas Bancárias")

tabs = st.tabs(["Visão Geral", "Nova Conta", "Transferência"])

# ─── Visão Geral ──────────────────────────────────────────────────────────────

with tabs[0]:
    contas_df = sh.get_contas()
    if contas_df.empty:
        st.info("Nenhuma conta cadastrada.")
    else:
        todas_entradas = sh.get_entradas()
        todos_gastos = sh.get_gastos()
        todas_transf = sh.get_transferencias()

        for _, row in contas_df.iterrows():
            saldo = utils.calcular_saldo_conta(
                row["nome"], todas_entradas, todos_gastos, todas_transf, contas_df
            )
            cor = "normal" if saldo >= 0 else "inverse"
            st.metric(
                label=f"🏦 {row['nome']} ({row['tipo']})",
                value=utils.fmt_brl(saldo),
                delta=f"Saldo inicial: {utils.fmt_brl(float(row['saldo_inicial']))}"
            )

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
        saldo_inicial = st.number_input("Saldo inicial (R$)", min_value=0.0, step=0.01, format="%.2f")
        submitted = st.form_submit_button("Salvar Conta", use_container_width=True)
    if submitted and nome:
        sh.add_conta(nome.strip(), tipo, saldo_inicial)
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
                valor = st.number_input("Valor (R$)", min_value=0.01, step=0.01, format="%.2f")
            with c2:
                destino = st.selectbox("Para", [c for c in contas], key="transf_destino")
                data_t = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            descricao = st.text_input("Descrição (opcional)")
            submitted = st.form_submit_button("Transferir", use_container_width=True)

        if submitted:
            if origem == destino:
                st.error("Conta de origem e destino devem ser diferentes.")
            else:
                sh.add_transferencia(data_t.isoformat(), valor, origem, destino, descricao)
                st.success(f"Transferência de {utils.fmt_brl(valor)} de {origem} para {destino} registrada!")
                st.rerun()
