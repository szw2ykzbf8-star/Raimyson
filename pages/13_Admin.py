import streamlit as st
import pandas as pd
from modules.auth import requer_perfil
from modules.google_sheets import ler_df, escrever_df, get_sheet

requer_perfil(["admin"])

st.title("⚙️ Administração do Sistema")
st.warning("⚠️ Esta página realiza operações irreversíveis. Use com cuidado.")

st.markdown("---")
st.subheader("🗑️ Limpeza de Dados")

def _safe_int(v):
    try:
        return int(float(v)) if str(v).strip() not in ("", "nan") else 0
    except Exception:
        return 0


@st.cache_data(ttl=30)
def _carregar_contagens():
    df_cotacoes     = ler_df("cotacoes")
    df_pedidos      = ler_df("pedidos")
    df_itens_pedido = ler_df("itens_pedido")
    df_respostas    = ler_df("respostas")
    df_compras      = ler_df("compras")
    df_itens_compra = ler_df("itens_compra")
    df_tokens       = ler_df("cotacao_tokens")
    df_cd           = ler_df("compras_diretas")
    df_hist         = ler_df("historico_precos")
    df_receb        = ler_df("itens_recebimento")
    df_nfe          = ler_df("nfe_mapeamento")

    ids_enc = set()
    if not df_cotacoes.empty and "status" in df_cotacoes.columns:
        ids_enc = set(
            df_cotacoes[df_cotacoes["status"] == "encerrada"]["id"]
            .apply(_safe_int).tolist()
        )

    ids_ped_enc = set()
    if not df_pedidos.empty and "cotacao_id" in df_pedidos.columns:
        ids_ped_enc = set(
            df_pedidos[df_pedidos["cotacao_id"].apply(_safe_int).isin(ids_enc)]["id"]
            .apply(_safe_int).tolist()
        )

    n_itens_ped = 0
    if not df_itens_pedido.empty and "pedido_id" in df_itens_pedido.columns:
        n_itens_ped = len(df_itens_pedido[
            df_itens_pedido["pedido_id"].apply(_safe_int).isin(ids_ped_enc)
        ])

    n_resp = 0
    if not df_respostas.empty and "cotacao_id" in df_respostas.columns:
        n_resp = len(df_respostas[
            df_respostas["cotacao_id"].apply(_safe_int).isin(ids_enc)
        ])

    ids_compras_enc = set()
    if not df_compras.empty and "cotacao_id" in df_compras.columns:
        ids_compras_enc = set(
            df_compras[df_compras["cotacao_id"].apply(_safe_int).isin(ids_enc)]["id"]
            .apply(_safe_int).tolist()
        )

    n_itens_compra = 0
    if not df_itens_compra.empty and "compra_id" in df_itens_compra.columns:
        n_itens_compra = len(df_itens_compra[
            df_itens_compra["compra_id"].apply(_safe_int).isin(ids_compras_enc)
        ])

    n_tok = 0
    if not df_tokens.empty and "cotacao_id" in df_tokens.columns:
        n_tok = len(df_tokens[
            df_tokens["cotacao_id"].apply(_safe_int).isin(ids_enc)
        ])

    n_cd = 0
    if not df_cd.empty and "cotacao_id" in df_cd.columns:
        n_cd = len(df_cd[
            df_cd["cotacao_id"].apply(_safe_int).isin(ids_enc)
        ])

    return {
        "ids_enc":          ids_enc,
        "ids_ped_enc":      ids_ped_enc,
        "ids_compras_enc":  ids_compras_enc,
        "n_cotacoes":       len(ids_enc),
        "n_pedidos":        len(ids_ped_enc),
        "n_itens_ped":      n_itens_ped,
        "n_resp":           n_resp,
        "n_compras":        len(ids_compras_enc),
        "n_itens_compra":   n_itens_compra,
        "n_tokens":         n_tok,
        "n_cd":             n_cd,
        "n_hist":           len(df_hist),
        "n_receb":          len(df_receb),
        "n_nfe":            len(df_nfe),
    }


info = _carregar_contagens()

st.markdown("#### O que será apagado:")

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Cotações encerradas e dados vinculados**")
    st.markdown(f"""
| Item | Qtd |
|---|---|
| Cotações encerradas | {info['n_cotacoes']} |
| Pedidos vinculados | {info['n_pedidos']} |
| Itens de pedido | {info['n_itens_ped']} |
| Respostas de fornecedores | {info['n_resp']} |
| Compras geradas | {info['n_compras']} |
| Itens de compra | {info['n_itens_compra']} |
| Tokens de acesso | {info['n_tokens']} |
| Itens Compra Direta | {info['n_cd']} |
""")
with col2:
    st.markdown("**Outros dados**")
    st.markdown(f"""
| Item | Qtd |
|---|---|
| Histórico de preços | {info['n_hist']} |
| Recebimento de NF | {info['n_receb']} |
| Mapeamento de NF | {info['n_nfe']} |
""")
    st.markdown("**Não será apagado:** Produtos, Fornecedores, Unidades, Usuários, cotações abertas/em andamento.")

st.markdown("---")

if info['n_cotacoes'] == 0 and info['n_hist'] == 0 and info['n_receb'] == 0:
    st.info("Nenhum dado para limpar no momento.")
else:
    st.markdown("#### Confirmação")
    st.caption("Digite **CONFIRMAR** para habilitar o botão de limpeza.")
    confirmacao = st.text_input("", placeholder="CONFIRMAR", label_visibility="collapsed")

    pode_executar = confirmacao.strip().upper() == "CONFIRMAR"

    if st.button(
        "🗑️ Executar Limpeza",
        disabled=not pode_executar,
        type="primary" if pode_executar else "secondary",
        use_container_width=True,
    ):
        erros = []
        sucessos = []

        try:
            ids_enc         = info["ids_enc"]
            ids_ped_enc     = info["ids_ped_enc"]
            ids_compras_enc = info["ids_compras_enc"]

            # -- ItensPedido
            df = ler_df("itens_pedido")
            if not df.empty and "pedido_id" in df.columns and ids_ped_enc:
                antes = len(df)
                df = df[~df["pedido_id"].apply(_safe_int).isin(ids_ped_enc)].reset_index(drop=True)
                escrever_df("itens_pedido", df)
                sucessos.append(f"ItensPedido: {antes - len(df)} linhas removidas")

            # -- Pedidos
            df = ler_df("pedidos")
            if not df.empty and "cotacao_id" in df.columns and ids_enc:
                antes = len(df)
                df = df[~df["cotacao_id"].apply(_safe_int).isin(ids_enc)].reset_index(drop=True)
                escrever_df("pedidos", df)
                sucessos.append(f"Pedidos: {antes - len(df)} removidos")

            # -- Respostas
            df = ler_df("respostas")
            if not df.empty and "cotacao_id" in df.columns and ids_enc:
                antes = len(df)
                df = df[~df["cotacao_id"].apply(_safe_int).isin(ids_enc)].reset_index(drop=True)
                escrever_df("respostas", df)
                sucessos.append(f"RespostasFornecedores: {antes - len(df)} removidas")

            # -- ItensCompra
            df = ler_df("itens_compra")
            if not df.empty and "compra_id" in df.columns and ids_compras_enc:
                antes = len(df)
                df = df[~df["compra_id"].apply(_safe_int).isin(ids_compras_enc)].reset_index(drop=True)
                escrever_df("itens_compra", df)
                sucessos.append(f"ItensCompra: {antes - len(df)} removidos")

            # -- Compras
            df = ler_df("compras")
            if not df.empty and "cotacao_id" in df.columns and ids_enc:
                antes = len(df)
                df = df[~df["cotacao_id"].apply(_safe_int).isin(ids_enc)].reset_index(drop=True)
                escrever_df("compras", df)
                sucessos.append(f"Compras: {antes - len(df)} removidas")

            # -- Tokens
            df = ler_df("cotacao_tokens")
            if not df.empty and "cotacao_id" in df.columns and ids_enc:
                antes = len(df)
                df = df[~df["cotacao_id"].apply(_safe_int).isin(ids_enc)].reset_index(drop=True)
                escrever_df("cotacao_tokens", df)
                sucessos.append(f"CotacaoTokens: {antes - len(df)} removidos")

            # -- ComprasDiretas
            df = ler_df("compras_diretas")
            if not df.empty and "cotacao_id" in df.columns and ids_enc:
                antes = len(df)
                df = df[~df["cotacao_id"].apply(_safe_int).isin(ids_enc)].reset_index(drop=True)
                escrever_df("compras_diretas", df)
                sucessos.append(f"ComprasDiretas: {antes - len(df)} removidas")

            # -- Cotacoes (por último)
            df = ler_df("cotacoes")
            if not df.empty and "status" in df.columns and ids_enc:
                antes = len(df)
                df = df[~df["id"].apply(_safe_int).isin(ids_enc)].reset_index(drop=True)
                escrever_df("cotacoes", df)
                sucessos.append(f"Cotacoes: {antes - len(df)} encerradas removidas")

            # -- HistoricoPrecos
            df = ler_df("historico_precos")
            if not df.empty:
                ws = get_sheet("historico_precos")
                headers = list(df.columns)
                ws.clear()
                ws.append_row(headers)
                sucessos.append(f"HistoricoPrecos: {len(df)} linhas limpas")

            # -- ItensRecebimento
            df = ler_df("itens_recebimento")
            if not df.empty:
                ws = get_sheet("itens_recebimento")
                headers = list(df.columns)
                ws.clear()
                ws.append_row(headers)
                sucessos.append(f"ItensRecebimento: {len(df)} linhas limpas")

            # -- NfeMapeamento
            df = ler_df("nfe_mapeamento")
            if not df.empty:
                ws = get_sheet("nfe_mapeamento")
                headers = list(df.columns)
                ws.clear()
                ws.append_row(headers)
                sucessos.append(f"NfeMapeamento: {len(df)} linhas limpas")

        except Exception as e:
            erros.append(str(e))

        st.cache_data.clear()

        if erros:
            st.error("Erros durante a limpeza:")
            for e in erros:
                st.write(e)

        if sucessos:
            st.success("✅ Limpeza concluída com sucesso!")
            for s in sucessos:
                st.write(f"• {s}")
            st.rerun()
