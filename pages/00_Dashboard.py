import streamlit as st
from modules.google_sheets import ler_df

usuario = st.session_state.get("usuario", {})

st.title("Dashboard")
st.markdown(f"Bem-vindo, **{usuario.get('nome', '')}**!")

col1, col2, col3, col4 = st.columns(4)

try:
    df_cotacoes = ler_df("cotacoes")
    abertas = len(df_cotacoes[df_cotacoes["status"] == "aberta"]) if not df_cotacoes.empty else 0
except Exception:
    abertas = "—"

try:
    df_pedidos = ler_df("pedidos")
    pendentes = len(df_pedidos[df_pedidos["status"] == "aberto"]) if not df_pedidos.empty else 0
except Exception:
    pendentes = "—"

try:
    df_forn = ler_df("fornecedores")
    forn_ativos = len(df_forn[df_forn["ativo"].apply(lambda v: v is True or str(v).upper() == "TRUE")]) if not df_forn.empty else 0
except Exception:
    forn_ativos = "—"

try:
    df_prod = ler_df("produtos")
    prod_ativos = len(df_prod[df_prod["ativo"].apply(lambda v: v is True or str(v).upper() == "TRUE")]) if not df_prod.empty else 0
except Exception:
    prod_ativos = "—"

with col1:
    st.metric("Cotações abertas", abertas)
with col2:
    st.metric("Pedidos pendentes", pendentes)
with col3:
    st.metric("Fornecedores ativos", forn_ativos)
with col4:
    st.metric("Produtos ativos", prod_ativos)

st.markdown("---")
st.info("Use o menu lateral para navegar entre os módulos.")
