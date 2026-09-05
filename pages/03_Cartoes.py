import streamlit as st
from src import auth, sheets as sh, utils

st.set_page_config(page_title="Cartões — FinTrack", page_icon="💳", layout="wide")
auth.require_auth()

st.title("💳 Cartões de Crédito")

# ─── Formulário de novo cartão ────────────────────────────────────────────────

with st.expander("➕ Novo Cartão", expanded=False):
    with st.form("form_cartao"):
        nome = st.text_input("Nome do cartão (ex: Nubank, Inter)")
        c1, c2 = st.columns(2)
        with c1:
            dia_fech = st.number_input("Dia de fechamento", 1, 31, 28)
        with c2:
            dia_venc = st.number_input("Dia de vencimento", 1, 31, 11)
        submitted = st.form_submit_button("Salvar Cartão", use_container_width=True)
    if submitted and nome:
        sh.add_cartao(nome.strip(), int(dia_fech), int(dia_venc))
        st.success(f"Cartão '{nome}' cadastrado!")
        st.rerun()

# ─── Lista de cartões ─────────────────────────────────────────────────────────

st.markdown("---")
df = sh.get_cartoes()

if df.empty:
    st.info("Nenhum cartão cadastrado.")
else:
    # Comprometimento futuro por cartão
    todos_gastos = sh.get_gastos()
    mes_atual = utils.mes_atual()

    for _, row in df.iterrows():
        st.subheader(f"💳 {row['nome']}")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Fecha dia", row["dia_fechamento"])
        with col2:
            st.metric("Vence dia", row["dia_vencimento"])
        with col3:
            if not todos_gastos.empty:
                mask = (todos_gastos["conta_cartao"] == row["nome"]) & \
                       (todos_gastos["forma_pagamento"] == "Crédito") & \
                       (todos_gastos["mes_referencia"] >= mes_atual)
                comprometido = todos_gastos[mask]["valor_parcela"].astype(float).sum()
            else:
                comprometido = 0
            st.metric("Comprometido futuro", utils.fmt_brl(comprometido))

        # Parcelas futuras por mês
        if not todos_gastos.empty:
            meses_futuros = utils.ultimos_meses(0)[0:1] + [
                utils.proximo_mes(mes_atual),
                utils.proximo_mes(utils.proximo_mes(mes_atual)),
                utils.proximo_mes(utils.proximo_mes(utils.proximo_mes(mes_atual))),
            ]
            mask_cartao = (todos_gastos["conta_cartao"] == row["nome"]) & \
                          (todos_gastos["forma_pagamento"] == "Crédito")
            df_cartao = todos_gastos[mask_cartao]
            if not df_cartao.empty:
                cols_meses = st.columns(len(meses_futuros))
                for i, m in enumerate(meses_futuros):
                    val = df_cartao[df_cartao["mes_referencia"] == m]["valor_parcela"].astype(float).sum()
                    with cols_meses[i]:
                        st.metric(utils.formatar_mes(m)[:3] + "/" + m[:4], utils.fmt_brl(val))

        # Excluir cartão
        if st.button(f"🗑️ Excluir {row['nome']}", key=f"del_c_{row['id']}"):
            st.session_state[f"confirm_del_c_{row['id']}"] = True

        if st.session_state.get(f"confirm_del_c_{row['id']}", False):
            pin = st.text_input("PIN de exclusão", type="password",
                                max_chars=6, key=f"pin_del_c_{row['id']}")
            c_ok, c_cancel = st.columns(2)
            with c_ok:
                if st.button("Confirmar exclusão", key=f"ok_del_c_{row['id']}"):
                    ok, msg = auth.verificar_pin_exclusao(pin)
                    if ok:
                        sh.delete_cartao(row["id"])
                        st.success("Cartão excluído.")
                        st.rerun()
                    else:
                        st.error(msg if msg != "bloqueado" else "🔒 PIN bloqueado!")
            with c_cancel:
                if st.button("Cancelar", key=f"cancel_del_c_{row['id']}"):
                    del st.session_state[f"confirm_del_c_{row['id']}"]
                    st.rerun()

        st.markdown("---")
