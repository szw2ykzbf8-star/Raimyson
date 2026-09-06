import streamlit as st
from datetime import date
from src import auth, sheets as sh, utils

st.set_page_config(page_title="Gastos — FinTrack", page_icon="💸", layout="wide")
auth.require_auth()

st.title("💸 Gastos")

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

# ─── Formulário de novo gasto ─────────────────────────────────────────────────

with st.expander("➕ Novo Gasto", expanded=False):
    cats_df = sh.get_categorias()
    contas_df = sh.get_contas()
    cartoes_df = sh.get_cartoes()
    cats = cats_df["nome"].tolist() if not cats_df.empty else []
    contas = contas_df["nome"].tolist() if not contas_df.empty else []
    cartoes = cartoes_df["nome"].tolist() if not cartoes_df.empty else []

    _k = st.session_state.get("_k_gasto", 0)
    with st.form(f"form_gasto_{_k}"):
        c1, c2, c3 = st.columns(3)
        with c1:
            data_g = st.date_input("Data da compra", value=date.today(), format="DD/MM/YYYY")
            categoria = st.selectbox("Categoria", cats)
        with c2:
            valor = st.number_input("Valor total (R$)", min_value=0.01, value=None, step=0.01, format="%.2f", placeholder="0,00")
            forma_pgto = st.selectbox("Forma de pagamento",
                                       ["Dinheiro", "Pix", "Débito", "Crédito"])
        with c3:
            num_parcelas = st.number_input("Nº de parcelas", min_value=1, max_value=72,
                                            value=1, step=1)
            if forma_pgto == "Crédito":
                conta_cartao = st.selectbox("Cartão", cartoes)
            else:
                conta_cartao = st.selectbox("Conta", contas)
        descricao = st.text_input("Descrição (opcional)")
        submitted = st.form_submit_button("Salvar Gasto", use_container_width=True)

    if submitted:
        if valor is None or valor <= 0:
            st.warning("Informe o valor do gasto.")
        elif forma_pgto == "Crédito":
            if not cartoes_df.empty:
                cartao_row = cartoes_df[cartoes_df["nome"] == conta_cartao].iloc[0]
                parcelas = utils.gerar_parcelas(
                    data_g.isoformat(), valor, int(num_parcelas),
                    int(cartao_row["dia_fechamento"]),
                    int(cartao_row["dia_vencimento"])
                )
                from itertools import islice
                id_grupo = None
                for p in parcelas:
                    rid = sh.add_gasto(
                        data_g.isoformat(), p["data_fatura"], p["mes_referencia"],
                        p["parcela_num"], p["total_parcelas"], p["valor_parcela"],
                        p["valor_total"], categoria, forma_pgto, conta_cartao,
                        descricao, id_grupo
                    )
                    if id_grupo is None:
                        id_grupo = rid
                st.success(f"Compra parcelada registrada! ({int(num_parcelas)}x de {utils.fmt_brl(parcelas[0]['valor_parcela'])})")
                st.session_state["_k_gasto"] = _k + 1
                st.rerun()
            else:
                st.error("Nenhum cartão cadastrado.")
        else:
            sh.add_gasto(
                data_g.isoformat(), data_g.isoformat(),
                utils.mes_str(data_g.year, data_g.month),
                1, 1, valor, valor, categoria, forma_pgto, conta_cartao, descricao
            )
            st.success(f"Gasto de {utils.fmt_brl(valor)} registrado!")
            st.session_state["_k_gasto"] = _k + 1
            st.rerun()

# ─── Lista de gastos ──────────────────────────────────────────────────────────

st.markdown("---")
df = sh.get_gastos(mes)

if df.empty:
    st.info("Nenhum gasto neste mês.")
else:
    total = df["valor_parcela"].astype(float).sum()
    st.markdown(f"**Total: {utils.fmt_brl(total)}**")

    # Filtro por categoria
    cats_presentes = ["Todas"] + sorted(df["categoria"].unique().tolist())
    filtro_cat = st.selectbox("Filtrar por categoria", cats_presentes)
    if filtro_cat != "Todas":
        df = df[df["categoria"] == filtro_cat]

    for cat in df["categoria"].unique():
        grupo = df[df["categoria"] == cat]
        total_cat = grupo["valor_parcela"].astype(float).sum()
        with st.expander(f"**{cat}** — {utils.fmt_brl(total_cat)}"):
            for _, row in grupo.iterrows():
                col_a, col_b, col_c, col_d, col_e = st.columns([2, 3, 2, 2, 1])
                with col_a:
                    st.write(utils.fmt_data(row["data_compra"]))
                with col_b:
                    desc = row["descricao"] or "—"
                    parcela_info = f" ({row['parcela_num']}/{row['total_parcelas']})" \
                        if int(row["total_parcelas"]) > 1 else ""
                    st.write(f"{desc}{parcela_info}")
                with col_c:
                    st.write(row["forma_pagamento"])
                with col_d:
                    st.write(f"**{utils.fmt_brl(float(row['valor_parcela']))}**")
                with col_e:
                    is_parcelado = int(row["total_parcelas"]) > 1
                    btn_label = "🗑️" if not is_parcelado else "🗑️*"
                    if st.button(btn_label, key=f"del_g_{row['id']}",
                                 help="* Exclui todas as parcelas"):
                        st.session_state[f"confirm_del_g_{row['id']}"] = True
                        st.session_state[f"is_grupo_{row['id']}"] = is_parcelado
                        st.session_state[f"id_grupo_{row['id']}"] = row["id_grupo"]

                if st.session_state.get(f"confirm_del_g_{row['id']}", False):
                    is_grupo = st.session_state.get(f"is_grupo_{row['id']}", False)
                    if is_grupo:
                        st.warning("⚠️ Isso excluirá TODAS as parcelas desta compra.")
                    pin = st.text_input("PIN de exclusão", type="password",
                                        max_chars=72, key=f"pin_del_g_{row['id']}")
                    c_ok, c_cancel = st.columns(2)
                    with c_ok:
                        if st.button("Confirmar", key=f"ok_del_g_{row['id']}"):
                            ok, msg = auth.verificar_pin_exclusao(pin)
                            if ok:
                                if is_grupo:
                                    sh.delete_gasto_grupo(st.session_state[f"id_grupo_{row['id']}"])
                                else:
                                    sh.delete_gasto(row["id"])
                                st.success("Gasto excluído.")
                                st.rerun()
                            else:
                                if msg == "bloqueado":
                                    st.error("🔒 PIN bloqueado!")
                                    st.rerun()
                                else:
                                    st.error(msg)
                    with c_cancel:
                        if st.button("Cancelar", key=f"cancel_del_g_{row['id']}"):
                            del st.session_state[f"confirm_del_g_{row['id']}"]
                            st.rerun()
