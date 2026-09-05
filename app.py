import streamlit as st

st.set_page_config(
    page_title="H Hotéis — Compras",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

from modules.auth import requer_login, criar_admin_inicial

try:
    criar_admin_inicial()
except Exception:
    pass

usuario = requer_login()

st.sidebar.title("🏨 H Hotéis Compras")
st.sidebar.markdown(f"**{usuario['nome']}**  \n*{usuario['perfil'].capitalize()}*")
st.sidebar.markdown("---")

st.title("Dashboard")
st.markdown(f"Bem-vindo, **{usuario['nome']}**!")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Cotações abertas", "—")
with col2:
    st.metric("Pedidos pendentes", "—")
with col3:
    st.metric("Fornecedores ativos", "—")
with col4:
    st.metric("Produtos ativos", "—")

st.markdown("---")
st.info("Use o menu lateral para navegar entre os módulos.")

if st.sidebar.button("Sair"):
    del st.session_state["usuario"]
    st.rerun()
