import hashlib
import streamlit as st
import pandas as pd
from modules.google_sheets import ler_df


def hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def autenticar(login: str, senha: str):
    df = ler_df("usuarios")
    if df.empty:
        return None
    usuario = df[(df["login"] == login) & (df["senha_hash"] == hash_senha(senha)) & (df["ativo"] == True)]
    if usuario.empty:
        return None
    return usuario.iloc[0].to_dict()


def login_page():
    st.title("H Hotéis — Sistema de Compras")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("Acesse sua conta")
        login = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            try:
                usuario = autenticar(login, senha)
                if usuario:
                    st.session_state["usuario"] = usuario
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")
            except Exception as e:
                st.error(f"Erro de conexão com Google Sheets: {e}")


def requer_login():
    if "usuario" not in st.session_state:
        login_page()
        st.stop()
    return st.session_state["usuario"]


def requer_perfil(perfis_permitidos: list):
    usuario = requer_login()
    if usuario["perfil"] not in perfis_permitidos:
        st.error("Você não tem permissão para acessar esta página.")
        st.stop()
    return usuario


def criar_admin_inicial():
    """Cria o usuário admin padrão se o banco estiver vazio."""
    from modules.google_sheets import append_linha
    df = ler_df("usuarios")
    if not df.empty:
        return
    append_linha("usuarios", [
        1, "Administrador", "admin", hash_senha("admin123"),
        "admin", "todos", True
    ])
