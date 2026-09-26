import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import datetime
from modules.auth import requer_permissao
from modules.google_sheets import ler_df, escrever_df

usuario = requer_permissao("ordem")
st.title("🛒 Pedidos de Compra")


def _safe_int(v):
    try:
        return int(float(v)) if str(v).strip() not in ("", "nan") else 0
    except Exception:
        return 0


def _safe_float(v, default=0.0):
    try:
        return float(v) if str(v).strip() not in ("", "nan") else default
    except Exception:
        return default


def _is_pending(v):
    return str(v).strip().lower() in ("false", "0", "")


def _addr(r):
    parts = [
        str(r.get("logradouro", "") or ""),
        str(r.get("numero", "") or ""),
        str(r.get("complemento", "") or ""),
        str(r.get("bairro", "") or ""),
        (str(r.get("cidade", "") or "") +
         ((" - " + str(r.get("estado", "") or "")) if r.get("estado") else "")),
    ]
    return ", ".join(p for p in parts if p.strip())


# ── Dados ─────────────────────────────────────────────────────────────────────
df_compras      = ler_df("compras")
df_itens_compra = ler_df("itens_compra")
df_fornecedores = ler_df("fornecedores")
df_produtos     = ler_df("produtos")
df_unidades     = ler_df("unidades")
df_respostas    = ler_df("respostas")
df_cotacoes     = ler_df("cotacoes")

cot_map = {_safe_int(r["id"]): str(r.get("nome", "") or "").strip() for _, r in df_cotacoes.iterrows()} if not df_cotacoes.empty else {}

prod_map = {_safe_int(r["id"]): r for _, r in df_produtos.iterrows()} if not df_produtos.empty else {}
forn_map = {_safe_int(r["id"]): r for _, r in df_fornecedores.iterrows()} if not df_fornecedores.empty else {}
unid_map = {str(r["nome"]): r for _, r in df_unidades.iterrows()} if not df_unidades.empty else {}

compras_pendentes = (
    df_compras[df_compras["pedido_gerado"].apply(_is_pending)]
    if not df_compras.empty else pd.DataFrame()
)


# ── Gerador de HTML ───────────────────────────────────────────────────────────
_CSS = """<style>
body{font-family:Arial,sans-serif;font-size:12px;color:#222;margin:20px}
h2{font-size:15px;margin:0 0 4px}
h3{font-size:12px;font-weight:bold;margin:14px 0 5px;
   border-bottom:1px solid #bbb;padding-bottom:3px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:3px 20px;
       margin-bottom:8px;line-height:1.65}
.status{color:#c00;font-weight:bold;margin:4px 0 14px;font-size:11px}
table{width:100%;border-collapse:collapse;margin-top:6px;font-size:11px}
th{background:#f2f2f2;border:1px solid #bbb;padding:5px 6px;text-align:left}
td{border:1px solid #ddd;padding:4px 6px;vertical-align:top}
.total{font-weight:bold;font-size:13px;margin:10px 0 4px}
.cmts{font-size:11px;margin-top:8px}
.section{margin-bottom:20px;page-break-after:always}
.section:last-child{page-break-after:auto}
@media print{.no-print{display:none!important}}
</style>"""


def _rows_html(itens_det):
    html = ""
    for it in itens_det:
        obs = str(it.get("obs_fornecedor", "") or "")
        obs_cell = obs if obs else "—"
        p = _safe_float(it.get("preco_unitario", 0))
        q = _safe_float(it.get("quantidade", 0))
        html += (
            f"<tr>"
            f"<td>{it.get('codigo','—')}</td>"
            f"<td>{it.get('descricao','—')}</td>"
            f"<td>{it.get('gram_sol','')}</td>"
            f"<td>{it.get('marca','')}</td>"
            f"<td style='font-size:10px'>{obs_cell}</td>"
            f"<td>{it.get('gram_inf','')}</td>"
            f"<td>R$ {p:.2f}</td>"
            f"<td>{q:g}</td>"
            f"<td>R$ {p*q:.2f}</td>"
            f"</tr>"
        )
    return html


def _secao(compra, forn, unid_info, itens_det, nome_cot=""):
    cid = _safe_int(compra["id"])
    data_str = str(compra.get("data_compra", ""))
    try:
        data_fmt = datetime.datetime.fromisoformat(data_str).strftime("%d/%m/%Y")
    except Exception:
        data_fmt = datetime.date.today().strftime("%d/%m/%Y")

    cot_display = nome_cot if nome_cot else (f"Cotação #{_safe_int(compra.get('cotacao_id', 0))}" if _safe_int(compra.get('cotacao_id', 0)) else "")
    cot_label = f" | Cotação: {cot_display}" if cot_display else ""
    total = sum(_safe_float(i["preco_unitario"]) * _safe_float(i["quantidade"]) for i in itens_det)
    forn_min = _safe_float(forn.get("pedido_minimo", 0))
    forn_min_str = f"R$ {forn_min:.2f}" if forn_min > 0 else "—"

    thead = (
        "<thead><tr>"
        "<th>Código</th><th>Produto</th><th>Gram. Solicitada</th>"
        "<th>Marca</th><th>Obs</th><th>Gram. Informada</th>"
        "<th>Preço Un.</th><th>Qtde.</th><th>Total</th>"
        "</tr></thead>"
    )

    return f"""<div class="section">
  <h2>Pedido nº {cid}{cot_label} | Data: {data_fmt}</h2>
  <p class="status">Status do pedido: Pedido realizado - aguardando fornecedor</p>

  <h3>Comprador</h3>
  <div class="grid2">
    <div>
      <b>Razão Social:</b> {str(unid_info.get('nome','') or '')}<br>
      <b>Nome Fantasia:</b> {str(unid_info.get('nome_fantasia','') or '')}<br>
      <b>CNPJ:</b> {str(unid_info.get('cnpj','') or '')}
    </div>
    <div>
      <b>Endereço:</b> {_addr(unid_info)}
    </div>
  </div>

  <h3>Fornecedor</h3>
  <div class="grid2">
    <div>
      <b>Razão Social:</b> {str(forn.get('razao_social','') or '')}<br>
      <b>Nome Fantasia:</b> {str(forn.get('nome_fantasia','') or '')}<br>
      <b>CNPJ:</b> {str(forn.get('cnpj','') or '')}<br>
      <b>Observação do Fornecedor:</b>
    </div>
    <div>
      <b>Telefone:</b> {str(forn.get('telefone','') or '')}<br>
      <b>Prazo para pagamento:</b><br>
      <b>Dias de entrega:</b><br>
      <b>Pedido mínimo:</b> {forn_min_str}
    </div>
  </div>

  <h3>Itens do Pedido</h3>
  <table>{thead}<tbody>{_rows_html(itens_det)}</tbody></table>

  <p class="cmts"><b>Comentários Gerais:</b> Pedido criado automaticamente pelo sistema de cotação</p>
  <p class="total">Total do Pedido: R$ {total:.2f}</p>
</div>"""


# ── UI principal ──────────────────────────────────────────────────────────────
if compras_pendentes.empty:
    st.info("Nenhum pedido de compra pendente para envio.")
else:
    forn_ids_list = sorted(compras_pendentes["fornecedor_id"].apply(_safe_int).unique())

    for fid in forn_ids_list:
        forn = forn_map.get(fid, {})
        nome_forn = str(forn.get("razao_social", f"#{fid}"))
        compras_forn = compras_pendentes[
            compras_pendentes["fornecedor_id"].apply(_safe_int) == fid
        ].sort_values("unidade")
        total_forn = compras_forn["valor_total"].apply(_safe_float).sum()
        n_hoteis = len(compras_forn)

        with st.expander(f"**{nome_forn}** — {n_hoteis} hotel(is) — R$ {total_forn:.2f}"):

            secoes_html = []
            compras_info = []
            total_itens  = 0

            for _, compra in compras_forn.iterrows():
                cid      = _safe_int(compra["id"])
                cot_id   = _safe_int(compra.get("cotacao_id", 0))
                unid_nome = str(compra.get("unidade", "") or "")
                unid_info = unid_map.get(unid_nome, {"nome": unid_nome, "nome_fantasia": unid_nome})

                itens_c = (
                    df_itens_compra[df_itens_compra["compra_id"].apply(_safe_int) == cid]
                    if not df_itens_compra.empty else pd.DataFrame()
                )

                itens_det = []
                for _, item in itens_c.iterrows():
                    pid  = _safe_int(item["produto_id"])
                    prod = prod_map.get(pid, {})

                    obs_forn = ""
                    marca_forn = ""
                    gram_inf = ""
                    if not df_respostas.empty:
                        resp = df_respostas[
                            (df_respostas["cotacao_id"].apply(_safe_int)   == cot_id) &
                            (df_respostas["fornecedor_id"].apply(_safe_int) == fid) &
                            (df_respostas["produto_id"].apply(_safe_int)   == pid)
                        ]
                        if not resp.empty:
                            obs_forn   = str(resp.iloc[0].get("observacao", "") or "")
                            marca_forn = str(resp.iloc[0].get("marca", "") or "")
                            _tipo      = str(resp.iloc[0].get("tipo_embalagem", "") or "")
                            _qtd_emb   = _safe_float(resp.iloc[0].get("qtd_por_embalagem", 1), 1.0)
                            gram_inf   = f"{_tipo} x{_qtd_emb:g}".strip() if _tipo and _qtd_emb > 1 else _tipo

                    itens_det.append({
                        "codigo":         str(prod.get("codigo", "") or "—"),
                        "descricao":      str(prod.get("descricao", f"Produto {pid}")),
                        "gram_sol":       str(prod.get("apresentacao", "") or ""),
                        "obs_fornecedor": obs_forn,
                        "marca":          marca_forn,
                        "gram_inf":       gram_inf,
                        "preco_unitario": _safe_float(item.get("preco_unitario", 0)),
                        "quantidade":     _safe_float(item.get("quantidade", 0)),
                    })

                nome_cot_compra = cot_map.get(cot_id, "")
                total_itens += len(itens_det)
                secoes_html.append(_secao(compra, forn, unid_info, itens_det, nome_cot_compra))
                compras_info.append({
                    "cid":      cid,
                    "label":    str(unid_info.get("nome_fantasia", unid_nome) or unid_nome),
                    "valor":    _safe_float(compra["valor_total"]),
                    "nome_cot": nome_cot_compra,
                })

            # Download (abrir no browser e Ctrl+P → Salvar PDF)
            total_geral = sum(info["valor"] for info in compras_info)
            total_geral_html = (
                f"<div style='margin-top:24px;padding:12px 0;border-top:2px solid #333;text-align:right'>"
                f"<b style='font-size:14px'>Total Geral do Fornecedor: R$ {total_geral:.2f}</b></div>"
            )
            html_completo = _CSS + "<body>" + "".join(secoes_html) + total_geral_html + "</body>"
            _nome_cot_grp = next((i["nome_cot"] for i in compras_info if i.get("nome_cot")), "")
            import re as _re
            nome_safe = _re.sub(r"[^\w]", "_", nome_forn)[:30]
            cot_safe  = _re.sub(r"[^\w]", "_", _nome_cot_grp)[:20] if _nome_cot_grp else ""
            fname     = f"{nome_safe}_{cot_safe}_{datetime.date.today()}.html" if cot_safe else f"{nome_safe}_{datetime.date.today()}.html"
            col_dl, _ = st.columns([2, 4])
            with col_dl:
                st.download_button(
                    "⬇️ Baixar pedido (imprimir / salvar PDF)",
                    data=html_completo.encode("utf-8"),
                    file_name=fname,
                    mime="text/html",
                    use_container_width=True,
                    key=f"dl_{fid}",
                )

            # Preview inline
            preview_h = min(total_itens * 52 + n_hoteis * 380, 950)
            components.html(html_completo, height=preview_h, scrolling=True)

            # Resumo das unidades
            st.markdown("**Unidades neste pedido:**")
            resumo_cols = st.columns(min(n_hoteis, 4))
            for i, info in enumerate(compras_info):
                resumo_cols[i % min(n_hoteis, 4)].caption(f"{info['label']} — R$ {info['valor']:.2f}")

            # Um único Enviado / Deletar para o fornecedor inteiro
            todos_cids = [info["cid"] for info in compras_info]
            col_env, col_del = st.columns(2)
            with col_env:
                if st.button("✅ Marcar tudo como enviado", key=f"env_{fid}", use_container_width=True):
                    for cid_env in todos_cids:
                        idx = df_compras[df_compras["id"].apply(_safe_int) == cid_env].index
                        if len(idx):
                            df_compras.at[idx[0], "pedido_gerado"] = "True"
                    escrever_df("compras", df_compras)
                    st.cache_data.clear()
                    st.rerun()
            with col_del:
                if st.button("🗑️ Deletar pedido", key=f"del_{fid}", use_container_width=True):
                    df_compras_upd = df_compras[~df_compras["id"].apply(_safe_int).isin(todos_cids)].reset_index(drop=True)
                    df_itens_upd = df_itens_compra[~df_itens_compra["compra_id"].apply(_safe_int).isin(todos_cids)].reset_index(drop=True)
                    escrever_df("compras", df_compras_upd)
                    escrever_df("itens_compra", df_itens_upd)
                    st.cache_data.clear()
                    st.rerun()
