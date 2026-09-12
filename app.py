import streamlit as st

st.set_page_config(
    page_title="H Hotéis — Compras",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

from modules.auth import criar_admin_inicial, login_page, pagina_trocar_senha

try:
    criar_admin_inicial()
except Exception:
    pass

usuario = st.session_state.get("usuario")

# ── Auth gate ────────────────────────────────────────────────────────────────
if usuario is None:
    pg = st.navigation([st.Page(login_page, title="Login", url_path="login")], position="hidden")
    pg.run()
    st.stop()

if usuario.get("trocar_senha") is True or str(usuario.get("trocar_senha", "")).upper() == "TRUE":
    pg = st.navigation(
        [st.Page(lambda: pagina_trocar_senha(usuario), title="Trocar Senha", url_path="trocar-senha")],
        position="hidden",
    )
    pg.run()
    st.stop()

# ── Sidebar header ───────────────────────────────────────────────────────────
st.sidebar.title("🏨 H Hotéis Compras")
st.sidebar.markdown(f"**{usuario['nome']}**  \n*{usuario['perfil'].capitalize()}*")

perfil = usuario["perfil"]

# ── Pages ────────────────────────────────────────────────────────────────────
dashboard    = st.Page("pages/00_Dashboard.py",    title="Dashboard",        icon="🏠", default=True)
minha_senha  = st.Page("pages/09_Minha_Senha.py",  title="Alterar Senha",    icon="🔐")
pedidos      = st.Page("pages/03_Pedidos.py",      title="Solicitações",     icon="📋")
cotacoes     = st.Page("pages/04_Cotacoes.py",     title="Cotações",         icon="💰")
analise      = st.Page("pages/05_Analise.py",      title="Análise de Preços",icon="📊")
ordem        = st.Page("pages/06_Pedido_Compra.py",title="Ordem de Compra",  icon="🛒")
produtos     = st.Page("pages/01_Produtos.py",     title="Produtos",         icon="📦")
fornecedores = st.Page("pages/02_Fornecedores.py", title="Fornecedores",     icon="🏭")
relatorios   = st.Page("pages/07_Relatorios.py",   title="Relatórios",       icon="📈")
configuracoes= st.Page("pages/08_Configuracoes.py",title="Configurações",    icon="⚙️")

# ── Navigation by profile ────────────────────────────────────────────────────
if perfil == "admin":
    nav = {
        "": [dashboard, minha_senha],
        "Fluxo de Compras": [pedidos, cotacoes, analise, ordem],
        "Cadastros": [produtos, fornecedores],
        "Análises": [relatorios],
        "Sistema": [configuracoes],
    }
elif perfil == "comprador":
    nav = {
        "": [dashboard, minha_senha],
        "Fluxo de Compras": [pedidos, cotacoes, analise, ordem],
        "Cadastros": [produtos, fornecedores],
        "Análises": [relatorios],
    }
else:  # digitador
    nav = {
        "": [dashboard, minha_senha],
        "Compras": [pedidos],
    }

pg = st.navigation(nav)

st.sidebar.markdown("---")
if st.sidebar.button("Sair", use_container_width=True):
    del st.session_state["usuario"]
    st.rerun()

pg.run()
