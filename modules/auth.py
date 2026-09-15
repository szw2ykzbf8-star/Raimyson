import hashlib
import streamlit as st
import pandas as pd
from modules.google_sheets import ler_df, escrever_df


def hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def validar_senha(senha: str) -> str | None:
    """Retorna mensagem de erro ou None se válida."""
    if len(senha) < 6:
        return "A senha deve ter no mínimo 6 caracteres."
    if len(senha) > 72:
        return "A senha deve ter no máximo 72 caracteres."
    return None


def alterar_senha(login: str, nova_senha: str):
    """Atualiza hash da senha e desativa flag trocar_senha."""
    df = ler_df("usuarios")
    idx = df[df["login"] == login].index
    if len(idx) == 0:
        return
    i = idx[0]
    df["senha_hash"] = df["senha_hash"].astype(object)
    df["trocar_senha"] = df["trocar_senha"].astype(object)
    df.at[i, "senha_hash"] = hash_senha(nova_senha)
    df.at[i, "trocar_senha"] = False
    escrever_df("usuarios", df)


def _bool(v) -> bool:
    return v is True or str(v).upper() == "TRUE"


def autenticar(login: str, senha: str):
    df = ler_df("usuarios")
    if df.empty:
        return None
    ativo_ok = df["ativo"].apply(_bool)
    usuario = df[(df["login"] == login) & (df["senha_hash"] == hash_senha(senha)) & ativo_ok]
    if usuario.empty:
        return None
    return usuario.iloc[0].to_dict()


def pagina_trocar_senha(usuario: dict):
    """Tela obrigatória de troca de senha no primeiro acesso."""
    st.title("🔑 Alteração de Senha")
    st.warning(
        "Por segurança, você precisa definir uma nova senha antes de continuar. "
        "Escolha uma senha forte com 6 a 72 caracteres."
    )
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if "troca_form_v" not in st.session_state:
            st.session_state["troca_form_v"] = 0
        with st.form(f"trocar_senha_{st.session_state['troca_form_v']}"):
            nova = st.text_input("Nova senha", type="password")
            confirma = st.text_input("Confirmar nova senha", type="password")
            if st.form_submit_button("Salvar nova senha", use_container_width=True):
                erro = validar_senha(nova)
                if erro:
                    st.error(erro)
                elif nova != confirma:
                    st.error("As senhas não coincidem.")
                else:
                    try:
                        alterar_senha(usuario["login"], nova)
                        st.session_state["usuario"]["trocar_senha"] = False
                        st.session_state["troca_form_v"] += 1
                        st.success("Senha alterada! Redirecionando…")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
    st.stop()


def login_page():
    st.title("H Hotéis — Sistema de Compras")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("Acesse sua conta")
        with st.form("login_form"):
            login = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar", use_container_width=True)
        if submitted:
            try:
                usuario = autenticar(login, senha)
                if usuario:
                    st.session_state["usuario"] = usuario
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")
            except Exception as e:
                st.error(f"Erro de conexão com Google Sheets: {e}")


_PERFIL_PADRAO_PERM = {
    "admin":     {"pedidos","cotacoes","analise","ordem","produtos","fornecedores","relatorios","configuracoes"},
    "comprador": {"pedidos","cotacoes","analise","ordem","produtos","fornecedores","relatorios"},
    "digitador": {"pedidos"},
}


def _get_permissoes(usuario: dict) -> set:
    perfil = usuario.get("perfil", "digitador")
    s = str(usuario.get("permissoes", "") or "").strip()
    perm = set(s.split(",")) if s else set(_PERFIL_PADRAO_PERM.get(perfil, {"pedidos"}))
    perm = {p.strip() for p in perm if p.strip()}
    if perfil == "admin":
        perm.add("configuracoes")
    else:
        perm.discard("configuracoes")
    return perm


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


def requer_permissao(chave: str):
    """Verifica se o usuário tem a permissão individual para esta página."""
    usuario = requer_login()
    if chave not in _get_permissoes(usuario):
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
        "admin", "todos", True, False, "",
    ])
