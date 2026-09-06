import streamlit as st
from datetime import date
from src import auth, sheets as sh, utils

st.set_page_config(page_title="Entradas — FinTrack", page_icon="💰", layout="wide")
auth.require_auth()

st.title("💰 Entradas")

# Seletor de mês
col1, col2, col3 = st.columns([1, 3, 1])
with col1:
    if st.button("◀", use_container_width=True):
        mes = st.session_state.get("mes_atual", utils.mes_atual())
        st.session_state["mes_atual"] = utils.mes_anterior(mes)
with col3:
    if st.button("▶", use_container_width=True):
        mes = st.session_state.get("mes_atual", utils.mes_atual())
        st.session_state["mes_atual"] = utils.proximo_mes(mes)
mes = st.session_state.get("mes_atual", utils.mes_atual())
with col2:
    st.markdown(f"<h3 style='text-align:center'>{utils.formatar_mes(mes)}</h3>",
                unsafe_allow_html=True)

# ─── Formulário de nova entrada ───────────────────────────────────────────────

with st.expander("➕ Nova Entrada", expanded=False):
    fontes_df = sh.get_fontes()
    contas_df = sh.get_contas()
    fontes = fontes_df["nome"].tolist() if not fontes_df.empty else []
    contas = contas_df["nome"].tolist() if not contas_df.empty else []

    _k = st.session_state.get("_k_entrada", 0)
    with st.form(f"form_entrada_{_k}"):
        c1, c2 = st.columns(2)
        with c1:
            data_e = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            fonte = st.selectbox("Fonte", fontes)
        with c2:
            valor = st.number_input("Valor (R$)", min_value=0.01, value=None, step=0.01, format="%.2f", placeholder="0,00")
            conta = st.selectbox("Conta de destino", contas)
        descricao = st.text_input("Descrição (opcional)")
        submitted = st.form_submit_button("Salvar Entrada", use_container_width=True)

    if submitted:
        if not fontes or not contas:
            st.error("Cadastre fontes de renda e contas bancárias antes de lançar entradas.")
        elif valor is None or valor <= 0:
            st.warning("Informe o valor da entrada.")
        else:
            sh.add_entrada(data_e.isoformat(), valor, fonte, conta, descricao)
            st.session_state["_k_entrada"] = _k + 1
            st.success(f"Entrada de {utils.fmt_brl(valor)} registrada!")
            st.rerun()

# ─── Lista de entradas ────────────────────────────────────────────────────────

st.markdown("---")
df = sh.get_entradas(mes)

if df.empty:
    st.info("Nenhuma entrada neste mês.")
else:
    total = df["valor"].astype(float).sum()
    st.markdown(f"**Total: {utils.fmt_brl(total)}**")

    # Agrupamento por fonte
    df_show = df[["data", "fonte", "conta", "valor", "descricao", "id"]].copy()
    df_show["valor_fmt"] = df_show["valor"].astype(float).apply(utils.fmt_brl)

    # Exibição por fonte
    for fonte_nome in df_show["fonte"].unique():
        grupo = df_show[df_show["fonte"] == fonte_nome]
        total_fonte = grupo["valor"].astype(float).sum()
        with st.expander(f"**{fonte_nome}** — {utils.fmt_brl(total_fonte)}"):
            for _, row in grupo.iterrows():
                col_a, col_b, col_c, col_d = st.columns([2, 3, 2, 1])
                with col_a:
                    st.write(utils.fmt_data(row["data"]))
                with col_b:
                    st.write(row["descricao"] or "—")
                with col_c:
                    st.write(f"**{row['valor_fmt']}**")
                with col_d:
                    if st.button("🗑️", key=f"del_e_{row['id']}"):
                        st.session_state[f"confirm_del_e_{row['id']}"] = True

                if st.session_state.get(f"confirm_del_e_{row['id']}", False):
                    pin = st.text_input("PIN de exclusão", type="password",
                                        max_chars=72, key=f"pin_del_e_{row['id']}")
                    c_ok, c_cancel = st.columns(2)
                    with c_ok:
                        if st.button("Confirmar exclusão", key=f"ok_del_e_{row['id']}"):
                            ok, msg = auth.verificar_pin_exclusao(pin)
                            if ok:
                                sh.delete_entrada(row["id"])
                                st.success("Entrada excluída.")
                                st.rerun()
                            else:
                                if msg == "bloqueado":
                                    st.error("🔒 PIN de exclusão bloqueado!")
                                    st.rerun()
                                else:
                                    st.error(msg)
                    with c_cancel:
                        if st.button("Cancelar", key=f"cancel_del_e_{row['id']}"):
                            del st.session_state[f"confirm_del_e_{row['id']}"]
                            st.rerun()
