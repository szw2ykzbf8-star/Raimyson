import streamlit as st
from src import auth, sheets as sh, utils

st.set_page_config(page_title="Contas Fixas — FinTrack", page_icon="📋", layout="wide")
auth.require_auth()

st.title("📋 Contas Fixas")
st.caption("Lançamentos que aparecem automaticamente todos os meses.")

# ─── Nova conta fixa ──────────────────────────────────────────────────────────

with st.expander("➕ Nova Conta Fixa", expanded=False):
    cats_df = sh.get_categorias()
    contas_df = sh.get_contas()
    cartoes_df = sh.get_cartoes()
    cats = cats_df["nome"].tolist() if not cats_df.empty else []
    contas = contas_df["nome"].tolist() if not contas_df.empty else []
    cartoes = cartoes_df["nome"].tolist() if not cartoes_df.empty else []

    _k = st.session_state.get("_k_fixa", 0)
    with st.form(f"form_fixa_{_k}"):
        c1, c2 = st.columns(2)
        with c1:
            nome = st.text_input("Nome (ex: Aluguel, Água, Netflix)")
            categoria = st.selectbox("Categoria", cats)
            dia_venc = st.number_input("Dia de vencimento", 1, 31, 10)
        with c2:
            valor_ref = st.number_input("Valor de referência (R$)", min_value=0.01, value=None, step=0.01, format="%.2f", placeholder="0,00")
            forma_pgto = st.selectbox("Forma de pagamento",
                                       ["Dinheiro", "Pix", "Débito", "Crédito", "Boleto"])
            if forma_pgto == "Crédito":
                conta_cartao = st.selectbox("Cartão", cartoes) if cartoes else st.text_input("Cartão")
            else:
                conta_cartao = st.selectbox("Conta", contas) if contas else st.text_input("Conta")
        submitted = st.form_submit_button("Salvar Conta Fixa", use_container_width=True)

    if submitted and nome:
        if valor_ref is None or valor_ref <= 0:
            st.warning("Informe o valor de referência.")
        else:
            mes_ini = utils.mes_atual()
            sh.add_fixa(nome.strip(), valor_ref, categoria, forma_pgto,
                        conta_cartao, int(dia_venc), mes_ini)
            st.session_state["_k_fixa"] = _k + 1
            st.success(f"Conta fixa '{nome}' cadastrada!")
            st.rerun()

# ─── Lista de contas fixas ────────────────────────────────────────────────────

st.markdown("---")
df = sh.get_fixas()

if df.empty:
    st.info("Nenhuma conta fixa cadastrada.")
else:
    total_ref = df["valor_referencia"].astype(float).sum()
    st.markdown(f"**Total de referência: {utils.fmt_brl(total_ref)}/mês**")
    st.markdown("")

    for _, row in df.iterrows():
        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
        with col1:
            st.write(f"**{row['nome']}**")
            st.caption(f"{row['categoria']} • {row['forma_pagamento']} • Vence dia {row['dia_vencimento']}")
        with col2:
            st.write(row["conta_cartao"])
        with col3:
            # Editar valor inline
            novo_valor = st.number_input(
                "Valor (R$)", value=float(row["valor_referencia"]),
                min_value=0.01, step=0.01, format="%.2f",
                key=f"val_fixa_{row['id']}",
                label_visibility="collapsed"
            )
            if novo_valor != float(row["valor_referencia"]):
                if st.button("💾", key=f"save_fixa_{row['id']}"):
                    sh.update_fixa_valor(row["id"], novo_valor)
                    st.success("Valor atualizado!")
                    st.rerun()
        with col4:
            st.write(utils.fmt_brl(float(row["valor_referencia"])))
        with col5:
            if st.button("🗑️", key=f"del_f_{row['id']}"):
                st.session_state[f"confirm_del_f_{row['id']}"] = True

        if st.session_state.get(f"confirm_del_f_{row['id']}", False):
            st.warning(f"Excluir '{row['nome']}' de todos os meses futuros?")
            pin = st.text_input("PIN de exclusão", type="password",
                                max_chars=72, key=f"pin_del_f_{row['id']}")
            c_ok, c_cancel = st.columns(2)
            with c_ok:
                if st.button("Confirmar", key=f"ok_del_f_{row['id']}"):
                    ok, msg = auth.verificar_pin_exclusao(pin)
                    if ok:
                        sh.delete_fixa(row["id"])
                        st.success("Conta fixa excluída.")
                        st.rerun()
                    else:
                        st.error(msg if msg != "bloqueado" else "🔒 PIN bloqueado!")
            with c_cancel:
                if st.button("Cancelar", key=f"cancel_del_f_{row['id']}"):
                    del st.session_state[f"confirm_del_f_{row['id']}"]
                    st.rerun()

        st.divider()
