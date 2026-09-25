import streamlit as st

st.set_page_config(
    page_title="H Hotéis — Compras",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Public quotation form (token-based, no auth required) ────────────────────
_token = st.query_params.get("token", "")
if _token:
    from modules.cotacao_publica import mostrar_pagina_publica
    mostrar_pagina_publica(_token)
    st.stop()

import os as _os

# ── First-run migration (PostgreSQL empty → import from Google Sheets) ────────
if _os.environ.get("DATABASE_URL"):
    _show_migration = False
    _migration_error = None
    try:
        from modules.database import ler_df as _ler_pg
        _df_users = _ler_pg("usuarios")
        if _df_users.empty:
            _show_migration = True
    except Exception as _e:
        _show_migration = True
        _migration_error = str(_e)

    if _show_migration:
        st.title("🔧 Configuração inicial")
        if _migration_error:
            st.error(f"Erro ao conectar no banco: {_migration_error}")
        else:
            st.warning(
                "O banco de dados PostgreSQL está vazio. "
                "Clique abaixo para importar os dados do Google Sheets."
            )
        if st.button("▶️ Migrar dados do Google Sheets → PostgreSQL", type="primary"):
            from modules.google_sheets import migrar_sheets_para_pg
            with st.spinner("Migrando… aguarde."):
                resultado = migrar_sheets_para_pg()
            erros = {k: v for k, v in resultado.items() if isinstance(v, str)}
            ok = {k: v for k, v in resultado.items() if not isinstance(v, str)}
            st.success(f"✅ Migração concluída! {len(ok)} tabelas importadas.")
            if erros:
                for k, e in erros.items():
                    st.caption(f"• {k}: {e}")
            st.cache_data.clear()
            st.rerun()
        st.stop()

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

# ── Permissions ───────────────────────────────────────────────────────────────
_PAGINAS_CONFIG = {
    "pedidos":      ("pages/03_Pedidos.py",      "Solicitações",      "📋"),
    "cotacoes":     ("pages/04_Cotacoes.py",     "Cotações",          "💰"),
    "analise":      ("pages/05_Analise.py",      "Análise de Preços", "📊"),
    "ordem":        ("pages/06_Pedido_Compra.py","Ordem de Compra",   "🛒"),
    "recebimento":  ("pages/10_Recebimento.py", "Recebimento NF-e",  "📥"),
    "compra_avulsa":("pages/11_Compra_Avulsa.py","Compra Avulsa",   "🧾"),
    "produtos":     ("pages/01_Produtos.py",     "Produtos",          "📦"),
    "fornecedores": ("pages/02_Fornecedores.py", "Fornecedores",      "🏭"),
    "relatorios":   ("pages/07_Relatorios.py",   "Relatórios",        "📈"),
    "configuracoes":("pages/08_Configuracoes.py","Configurações",     "⚙️"),
}
_PERFIL_PADRAO = {
    "admin":     ["pedidos","cotacoes","analise","ordem","recebimento","compra_avulsa","produtos","fornecedores","relatorios","configuracoes"],
    "comprador": ["pedidos","cotacoes","analise","ordem","recebimento","compra_avulsa","produtos","fornecedores","relatorios"],
    "digitador": ["pedidos"],
}

permissoes_str = str(usuario.get("permissoes", "") or "").strip()
if permissoes_str:
    permissoes = set(p.strip() for p in permissoes_str.split(",") if p.strip())
else:
    permissoes = set(_PERFIL_PADRAO.get(perfil, ["pedidos"]))

# configuracoes é sempre do admin e nunca de outros perfis
if perfil == "admin":
    permissoes.add("configuracoes")
else:
    permissoes.discard("configuracoes")


def _pg(chave):
    path, title, icon = _PAGINAS_CONFIG[chave]
    return st.Page(path, title=title, icon=icon)


# ── Pages ────────────────────────────────────────────────────────────────────
dashboard   = st.Page("pages/00_Dashboard.py",   title="Dashboard",     icon="🏠", default=True)
minha_senha = st.Page("pages/09_Minha_Senha.py", title="Alterar Senha", icon="🔐")

nav = {"": [dashboard, minha_senha]}

fluxo = [k for k in ["pedidos","cotacoes","analise","ordem","recebimento","compra_avulsa"] if k in permissoes]
if fluxo:
    nav["Fluxo de Compras"] = [_pg(k) for k in fluxo]

cadastros = [k for k in ["produtos","fornecedores"] if k in permissoes]
if cadastros:
    nav["Cadastros"] = [_pg(k) for k in cadastros]

if "relatorios" in permissoes:
    nav["Análises"] = [_pg("relatorios")]

if "configuracoes" in permissoes:
    nav["Sistema"] = [_pg("configuracoes")]

pg = st.navigation(nav)

st.sidebar.markdown("---")
if st.sidebar.button("Sair", use_container_width=True):
    del st.session_state["usuario"]
    st.rerun()

pg.run()
