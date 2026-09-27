import streamlit as st
import pandas as pd
import datetime
from modules.auth import requer_permissao
from modules.google_sheets import ler_df, escrever_df, append_linha, ler_categorias

usuario = requer_permissao("pedidos")

st.title("📋 Solicitações de Compra")

df_produtos = ler_df("produtos")
df_pedidos  = ler_df("pedidos")
df_itens    = ler_df("itens_pedido")

perfil = usuario["perfil"]
unidades_acesso = usuario["unidades_acesso"]
if unidades_acesso == "todos":
    unidades_disponiveis = ler_df("unidades")["nome"].tolist()
else:
    unidades_disponiveis = [u.strip() for u in str(unidades_acesso).split(",")]


def _safe_int(v):
    try:
        return int(float(v)) if str(v).strip() not in ("", "nan") else 0
    except Exception:
        return 0


def _next_id(df, col="id"):
    if df.empty or col not in df.columns:
        return 1
    try:
        return int(df[col].apply(_safe_int).max()) + 1
    except Exception:
        return 1


# ── Produtos ativos organizados por categoria (usado em Nova Solicitação e Editar) ──
produtos_ativos = (
    df_produtos[df_produtos["ativo"].astype(str).str.upper().isin(["TRUE", "1", "SIM"])].copy()
    if not df_produtos.empty else pd.DataFrame()
)
if not produtos_ativos.empty:
    if "categoria" not in produtos_ativos.columns:
        produtos_ativos["categoria"] = ""
    produtos_ativos["categoria"] = produtos_ativos["categoria"].fillna("").astype(str).str.strip()
    produtos_ativos = produtos_ativos.sort_values(
        "descricao", key=lambda x: x.str.lower(), ignore_index=True
    )
    _ordem_cats    = ler_categorias() + [""]
    _cats_presentes = [c for c in _ordem_cats if c in produtos_ativos["categoria"].values]
else:
    _cats_presentes = []

CSS = """
<style>
.prod-row {
    display: flex;
    align-items: baseline;
    width: 100%;
    gap: 0;
}
.prod-nome {
    white-space: nowrap;
    font-weight: 600;
    font-size: 14px;
}
.prod-unidade {
    white-space: nowrap;
    font-size: 12px;
    color: #888;
    margin-left: 4px;
}
.prod-dots {
    flex: 1;
    border-bottom: 1.5px dotted #bbb;
    margin: 0 8px 4px 8px;
    min-width: 20px;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def _renderizar_form_produtos(sufixo: str, qtds_pre: dict) -> dict:
    """Renderiza o formulário de produtos com quantidades pré-preenchidas.
    Retorna dict {produto_id: quantidade} com os itens preenchidos."""
    itens = {}
    for cat in _cats_presentes:
        grupo = produtos_ativos[produtos_ativos["categoria"] == cat]
        if grupo.empty:
            continue
        cat_label = cat if cat else "Sem categoria"
        with st.expander(f"📦 {cat_label}", expanded=True):
            for _, prod in grupo.iterrows():
                pid = str(prod["id"])
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(
                        f'<div class="prod-row">'
                        f'<span class="prod-nome">{prod["descricao"]}</span>'
                        f'<span class="prod-unidade">— {prod["unidade_base"]}</span>'
                        f'<span class="prod-dots"></span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    if prod.get("observacao"):
                        st.caption(prod["observacao"])
                with col2:
                    qtd = st.number_input(
                        "Qtd",
                        min_value=0.0,
                        step=0.5,
                        value=float(qtds_pre.get(pid, 0.0)),
                        key=f"qtd_{pid}_{sufixo}",
                        label_visibility="collapsed",
                    )
                    if qtd > 0:
                        itens[prod["id"]] = qtd
    return itens


# ── Session state ────────────────────────────────────────────────────────────
if "pedido_form_v" not in st.session_state:
    st.session_state["pedido_form_v"] = 0
if "editando_pedido" not in st.session_state:
    st.session_state["editando_pedido"] = None

tab_novo, tab_abertos = st.tabs(["Nova Solicitação", "Solicitações Abertas"])

# ── TAB: NOVA SOLICITAÇÃO ────────────────────────────────────────────────────
with tab_novo:
    unidade = st.selectbox("Unidade", unidades_disponiveis)

    if produtos_ativos.empty:
        st.warning("Nenhum produto ativo cadastrado.")
    else:
        st.markdown("Preencha a quantidade desejada. Deixe em branco os produtos que não precisa.")
        fv = st.session_state["pedido_form_v"]
        itens_pedido = _renderizar_form_produtos(sufixo=f"novo_{fv}", qtds_pre={})

        if st.button("Enviar Solicitação", type="primary"):
            if not itens_pedido:
                st.error("Selecione ao menos um produto com quantidade.")
            else:
                try:
                    novo_id = _next_id(df_pedidos)
                    item_id = _next_id(df_itens)
                    append_linha("pedidos", [
                        novo_id, unidade, "aberto",
                        usuario["nome"], datetime.datetime.now().isoformat(), "", "",
                    ])
                    for prod_id, qtd in itens_pedido.items():
                        append_linha("itens_pedido", [item_id, novo_id, prod_id, qtd])
                        item_id += 1
                    st.session_state["pedido_form_v"] += 1
                    st.cache_data.clear()
                    st.success(f"Solicitação #{novo_id} enviada para {unidade}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar solicitação: {e}")

# ── TAB: SOLICITAÇÕES ABERTAS ────────────────────────────────────────────────
with tab_abertos:
    if df_pedidos.empty:
        st.info("Nenhuma solicitação aberta.")
    else:
        pedidos_abertos = df_pedidos[df_pedidos["status"] == "aberto"].copy()
        if unidades_acesso != "todos":
            pedidos_abertos = pedidos_abertos[pedidos_abertos["unidade"].isin(unidades_disponiveis)]

        if pedidos_abertos.empty:
            st.info("Nenhuma solicitação aberta para sua(s) unidade(s).")
        else:
            for _, ped in pedidos_abertos.iterrows():
                ped_id     = _safe_int(ped["id"])
                criado_por = str(ped.get("criado_por", "") or "")
                data_label = str(ped.get("data_criacao", ""))[:10] or "—"

                pode_editar   = perfil == "admin" or criado_por == usuario["nome"]
                pode_bloquear = perfil in ["admin", "comprador"]

                with st.expander(f"#{ped_id} — {ped['unidade']} — {data_label} — por {criado_por}"):
                    itens = (
                        df_itens[df_itens["pedido_id"].apply(_safe_int) == ped_id]
                        if not df_itens.empty else pd.DataFrame()
                    )

                    # ── Modo edição ──────────────────────────────────────────
                    if st.session_state["editando_pedido"] == ped_id:
                        st.caption("✏️ Editando solicitação — ajuste as quantidades e salve.")

                        qtds_pre = {}
                        if not itens.empty:
                            for _, it in itens.iterrows():
                                try:
                                    qtds_pre[str(it["produto_id"])] = float(it["quantidade"])
                                except Exception:
                                    pass

                        novos_itens = _renderizar_form_produtos(
                            sufixo=f"edit_{ped_id}", qtds_pre=qtds_pre
                        )

                        col_s, col_c = st.columns(2)
                        with col_s:
                            if st.button("💾 Salvar Alterações", key=f"salvar_edit_{ped_id}", type="primary", use_container_width=True):
                                if not novos_itens:
                                    st.error("Selecione ao menos um produto com quantidade.")
                                else:
                                    try:
                                        df_itens_reload = ler_df("itens_pedido")
                                        df_sem_este = (
                                            df_itens_reload[df_itens_reload["pedido_id"].apply(_safe_int) != ped_id]
                                            if not df_itens_reload.empty else pd.DataFrame()
                                        )
                                        escrever_df("itens_pedido", df_sem_este)
                                        item_id = _next_id(df_sem_este)
                                        for prod_id, qtd in novos_itens.items():
                                            append_linha("itens_pedido", [item_id, ped_id, prod_id, qtd])
                                            item_id += 1
                                        st.session_state["editando_pedido"] = None
                                        st.cache_data.clear()
                                        st.success("Solicitação atualizada!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao salvar: {e}")
                        with col_c:
                            if st.button("✖ Cancelar", key=f"cancelar_edit_{ped_id}", use_container_width=True):
                                st.session_state["editando_pedido"] = None
                                st.rerun()

                    # ── Modo visualização ────────────────────────────────────
                    else:
                        if not itens.empty and not df_produtos.empty:
                            itens_display = itens.merge(
                                df_produtos[["id", "descricao", "unidade_base"]],
                                left_on="produto_id", right_on="id", how="left"
                            )[["descricao", "unidade_base", "quantidade"]]
                            st.dataframe(itens_display, use_container_width=True, hide_index=True)

                        n_botoes = sum([pode_editar, pode_bloquear])
                        if n_botoes:
                            cols = st.columns(n_botoes)
                            ci = 0
                            if pode_editar:
                                with cols[ci]:
                                    if st.button("✏️ Editar", key=f"editar_{ped_id}", use_container_width=True):
                                        st.session_state["editando_pedido"] = ped_id
                                        st.rerun()
                                ci += 1
                            if pode_bloquear:
                                with cols[ci]:
                                    if st.button("🔒 Bloquear (consolidar)", key=f"bloquear_{ped_id}", use_container_width=True):
                                        from modules.google_sheets import atualizar_linha
                                        atualizar_linha("pedidos", ped["id"], {
                                            "status": "bloqueado",
                                            "data_bloqueio": datetime.datetime.now().isoformat(),
                                        })
                                        st.success("Pedido bloqueado!")
                                        st.cache_data.clear()
                                        st.rerun()
