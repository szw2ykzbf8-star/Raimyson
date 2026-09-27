import streamlit as st
from modules.auth import requer_login
from modules.google_sheets import ler_df

usuario = requer_login()

st.title("Dashboard")
st.markdown(f"Bem-vindo, **{usuario.get('nome', '')}**!")

perfil = usuario.get("perfil", "")
unidades_acesso = usuario.get("unidades_acesso", "")

col1, col2, col3, col4 = st.columns(4)

try:
    df_cotacoes = ler_df("cotacoes")
    abertas = len(df_cotacoes[df_cotacoes["status"] == "aberta"]) if not df_cotacoes.empty else 0
except Exception:
    abertas = "—"

try:
    df_pedidos = ler_df("pedidos")
    if not df_pedidos.empty:
        pendentes = len(df_pedidos[df_pedidos["status"] == "aberto"])
        bloqueados = len(df_pedidos[df_pedidos["status"] == "bloqueado"])
    else:
        pendentes = 0
        bloqueados = 0
except Exception:
    pendentes = "—"
    bloqueados = "—"

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
    st.metric("Solicitações abertas", pendentes)
with col3:
    st.metric("Solicitações bloqueadas", bloqueados)
with col4:
    st.metric("Fornecedores ativos", forn_ativos)

col5, col6 = st.columns([1, 3])
with col5:
    st.metric("Produtos ativos", prod_ativos)

# ── Notificação: Solicitações aguardando consolidação (admin/comprador) ──────
if perfil in ("admin", "comprador") and isinstance(pendentes, int) and pendentes > 0:
    try:
        pedidos_abertos = df_pedidos[df_pedidos["status"] == "aberto"].copy()
        if unidades_acesso != "todos":
            unidades_disp = [u.strip() for u in str(unidades_acesso).split(",")]
            pedidos_abertos = pedidos_abertos[pedidos_abertos["unidade"].isin(unidades_disp)]
        if not pedidos_abertos.empty:
            n_ped = len(pedidos_abertos)
            n_unid = pedidos_abertos["unidade"].nunique()
            st.warning(
                f"📋 **{n_ped} solicitação(ões) aberta(s)** aguardando consolidação em "
                f"{n_unid} unidade(s). Acesse **Solicitações** para revisar e bloquear."
            )
    except Exception:
        pass

# ── Alerta: Compras Diretas pendentes ────────────────────────────────────────
try:
    df_cd = ler_df("compras_diretas")
    if not df_cd.empty:
        cd_pend = df_cd[~df_cd["comprado"].apply(lambda v: str(v).strip().lower() in ("true", "1"))]
        if not cd_pend.empty:
            n_itens = len(cd_pend)
            n_unids = cd_pend["unidade"].nunique()
            st.warning(
                f"🛒 **{n_itens} item(ns) de Compra Direta pendente(s)** em {n_unids} unidade(s). "
                "Acesse **Ordem de Compra → Compra Direta** para marcar como comprado."
            )
except Exception:
    pass

st.markdown("---")
st.info("Use o menu lateral para navegar entre os módulos.")
