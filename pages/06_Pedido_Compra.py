import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import datetime
import io
from modules.auth import requer_permissao
from modules.google_sheets import ler_df, escrever_df

usuario = requer_permissao("ordem")
st.title("🛒 Ordem de Compra")


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
df_compras_dir  = ler_df("compras_diretas")

cot_map = {_safe_int(r["id"]): str(r.get("nome", "") or "").strip() for _, r in df_cotacoes.iterrows()} if not df_cotacoes.empty else {}

prod_map = {_safe_int(r["id"]): r for _, r in df_produtos.iterrows()} if not df_produtos.empty else {}
forn_map = {_safe_int(r["id"]): r for _, r in df_fornecedores.iterrows()} if not df_fornecedores.empty else {}
unid_map = {str(r["nome"]): r for _, r in df_unidades.iterrows()} if not df_unidades.empty else {}

compras_pendentes = (
    df_compras[df_compras["pedido_gerado"].apply(_is_pending)]
    if not df_compras.empty else pd.DataFrame()
)


def _tentar_encerrar_cotacao(cot_id_chk, df_compras_all, df_cd_all):
    """Close cotação if all regular orders sent and all direct purchases done."""
    mask_cot = df_compras_all["cotacao_id"].apply(_safe_int) == cot_id_chk
    todas_compras = df_compras_all[mask_cot]
    compras_ok = (
        not todas_compras.empty and
        todas_compras["pedido_gerado"].apply(
            lambda v: str(v).strip().lower() not in ("false", "0", "")
        ).all()
    )
    mask_cd = df_cd_all["cotacao_id"].apply(_safe_int) == cot_id_chk
    todas_cd = df_cd_all[mask_cd]
    cd_ok = todas_cd.empty or todas_cd["comprado"].apply(
        lambda v: str(v).strip().lower() not in ("false", "0", "")
    ).all()
    if compras_ok and cd_ok:
        df_cot_upd = ler_df("cotacoes")
        idx_cot = df_cot_upd[df_cot_upd["id"].apply(_safe_int) == cot_id_chk].index
        if len(idx_cot):
            df_cot_upd.at[idx_cot[0], "status"] = "encerrada"
            escrever_df("cotacoes", df_cot_upd)


# ── Gerador de HTML (preview inline) ─────────────────────────────────────────
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


# ── Gerador de PDF com reportlab ──────────────────────────────────────────────
def _gerar_pdf(secoes_data: list, nome_fornecedor: str, total_geral: float) -> bytes:
    """Gera PDF usando reportlab. Retorna bytes do PDF."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()
    s_title  = ParagraphStyle("ptitle",  parent=styles["Heading2"], fontSize=13, spaceAfter=2)
    s_h3     = ParagraphStyle("ph3",     parent=styles["Heading3"], fontSize=10, spaceBefore=10, spaceAfter=4)
    s_normal = ParagraphStyle("pnormal", parent=styles["Normal"],   fontSize=9,  leading=13)
    s_small  = ParagraphStyle("psmall",  parent=styles["Normal"],   fontSize=8,  leading=11)
    s_status = ParagraphStyle("pstatus", parent=styles["Normal"],   fontSize=9,  textColor=colors.red, spaceAfter=8)
    s_total  = ParagraphStyle("ptotal",  parent=styles["Normal"],   fontSize=11, fontName="Helvetica-Bold")
    s_gtotal = ParagraphStyle("pgtotal", parent=styles["Normal"],   fontSize=12, fontName="Helvetica-Bold", alignment=TA_RIGHT)

    col_headers = ["Código", "Produto", "Gram. Sol.", "Marca", "Obs", "Gram. Inf.", "Preço Un.", "Qtde.", "Total"]
    col_widths  = [1.5*cm, 4.8*cm, 2.2*cm, 2.2*cm, 2.5*cm, 2.2*cm, 1.8*cm, 1.3*cm, 1.8*cm]

    story = []

    for _sec_idx, sec in enumerate(secoes_data):
        compra   = sec["compra"]
        forn     = sec["forn"]
        unid     = sec["unid"]
        itens    = sec["itens"]
        nome_cot = sec.get("nome_cot", "")

        if _sec_idx > 0:
            story.append(PageBreak())

        cid = _safe_int(compra["id"])
        data_str = str(compra.get("data_compra", ""))
        try:
            data_fmt = datetime.datetime.fromisoformat(data_str).strftime("%d/%m/%Y")
        except Exception:
            data_fmt = datetime.date.today().strftime("%d/%m/%Y")

        cot_display = nome_cot if nome_cot else (f"Cotação #{_safe_int(compra.get('cotacao_id',0))}" if _safe_int(compra.get('cotacao_id',0)) else "")
        cot_suffix  = f" | Cotação: {cot_display}" if cot_display else ""

        story.append(Paragraph(f"Pedido nº {cid}{cot_suffix} | Data: {data_fmt}", s_title))
        story.append(Paragraph("Status: Pedido realizado - aguardando fornecedor", s_status))

        # Comprador / Fornecedor side-by-side table
        comp_text = (
            f"<b>Razão Social:</b> {str(unid.get('nome','') or '')}<br/>"
            f"<b>Nome Fantasia:</b> {str(unid.get('nome_fantasia','') or '')}<br/>"
            f"<b>CNPJ:</b> {str(unid.get('cnpj','') or '')}<br/>"
            f"<b>Endereço:</b> {_addr(unid)}"
        )
        forn_min = _safe_float(forn.get("pedido_minimo", 0))
        forn_min_str = f"R$ {forn_min:.2f}" if forn_min > 0 else "—"
        forn_text = (
            f"<b>Razão Social:</b> {str(forn.get('razao_social','') or '')}<br/>"
            f"<b>Nome Fantasia:</b> {str(forn.get('nome_fantasia','') or '')}<br/>"
            f"<b>CNPJ:</b> {str(forn.get('cnpj','') or '')}<br/>"
            f"<b>Telefone:</b> {str(forn.get('telefone','') or '')}<br/>"
            f"<b>Pedido mínimo:</b> {forn_min_str}"
        )
        info_table = Table(
            [[Paragraph(f"<b>Comprador</b><br/>{comp_text}", s_small),
              Paragraph(f"<b>Fornecedor</b><br/>{forn_text}", s_small)]],
            colWidths=[9*cm, 9*cm],
        )
        info_table.setStyle(TableStyle([
            ("BOX",        (0,0), (-1,-1), 0.5, colors.grey),
            ("INNERGRID",  (0,0), (-1,-1), 0.5, colors.grey),
            ("VALIGN",     (0,0), (-1,-1), "TOP"),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 6))

        # Items table
        total_sec = sum(_safe_float(i["preco_unitario"]) * _safe_float(i["quantidade"]) for i in itens)
        rows = [col_headers]
        for it in itens:
            p = _safe_float(it.get("preco_unitario", 0))
            q = _safe_float(it.get("quantidade", 0))
            obs = str(it.get("obs_fornecedor", "") or "") or "—"
            rows.append([
                it.get("codigo", "—"),
                Paragraph(str(it.get("descricao", "—") or "—"), s_small),
                Paragraph(str(it.get("gram_sol", "") or ""), s_small),
                Paragraph(str(it.get("marca", "") or ""), s_small),
                Paragraph(obs, s_small),
                Paragraph(str(it.get("gram_inf", "") or ""), s_small),
                f"R$ {p:.2f}",
                f"{q:g}",
                f"R$ {p*q:.2f}",
            ])

        items_t = Table(rows, colWidths=col_widths, repeatRows=1)
        items_t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), colors.Color(0.95, 0.95, 0.95)),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 8),
            ("BOX",           (0,0), (-1,-1), 0.5, colors.grey),
            ("INNERGRID",     (0,0), (-1,-1), 0.3, colors.lightgrey),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ]))
        story.append(items_t)
        story.append(Paragraph(f"Total do Pedido: R$ {total_sec:.2f}", s_total))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey, spaceAfter=8))
        story.append(Spacer(1, 4))

    story.append(Paragraph(f"Total Geral do Fornecedor: R$ {total_geral:.2f}", s_gtotal))

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ── UI principal ──────────────────────────────────────────────────────────────
tab_regular, tab_direta = st.tabs(["📦 Pedidos Regulares", "🛒 Compra Direta"])

# ── Aba: Pedidos Regulares ─────────────────────────────────────────────────────
with tab_regular:
    if compras_pendentes.empty:
        st.info("Nenhum pedido de compra pendente para envio.")
    else:
        forn_ids_list = sorted(compras_pendentes["fornecedor_id"].apply(_safe_int).unique())

        for fid in forn_ids_list:
            forn = forn_map.get(fid, {})
            nome_forn = str(forn.get("nome_fantasia") or forn.get("razao_social") or f"#{fid}")
            compras_forn = compras_pendentes[
                compras_pendentes["fornecedor_id"].apply(_safe_int) == fid
            ].sort_values("unidade")
            total_forn = compras_forn["valor_total"].apply(_safe_float).sum()
            n_hoteis = len(compras_forn)

            with st.expander(f"**{nome_forn}** — {n_hoteis} hotel(is) — R$ {total_forn:.2f}"):

                secoes_html = []
                secoes_pdf  = []
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
                    secoes_pdf.append({
                        "compra":   compra,
                        "forn":     forn,
                        "unid":     unid_info,
                        "itens":    itens_det,
                        "nome_cot": nome_cot_compra,
                    })
                    compras_info.append({
                        "cid":      cid,
                        "label":    str(unid_info.get("nome_fantasia", unid_nome) or unid_nome),
                        "valor":    _safe_float(compra["valor_total"]),
                        "nome_cot": nome_cot_compra,
                    })

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
                base_name = f"{nome_safe}_{cot_safe}_{datetime.date.today()}" if cot_safe else f"{nome_safe}_{datetime.date.today()}"

                col_pdf, col_dl, _ = st.columns([2, 2, 2])
                with col_pdf:
                    try:
                        pdf_bytes = _gerar_pdf(secoes_pdf, nome_forn, total_geral)
                        st.download_button(
                            "📄 Baixar PDF",
                            data=pdf_bytes,
                            file_name=f"{base_name}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"pdf_{fid}",
                        )
                    except Exception as e:
                        st.caption(f"PDF indisponível: {e}")
                with col_dl:
                    st.download_button(
                        "⬇️ Baixar PDF (HTML)",
                        data=html_completo.encode("utf-8"),
                        file_name=f"{base_name}.html",
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
                    if st.button("✅ Enviado", key=f"env_{fid}", use_container_width=True):
                        for cid_env in todos_cids:
                            idx = df_compras[df_compras["id"].apply(_safe_int) == cid_env].index
                            if len(idx):
                                df_compras.at[idx[0], "pedido_gerado"] = "True"
                        escrever_df("compras", df_compras)

                        # Encerra cotação se todos os pedidos enviados e compras_diretas concluídas
                        cot_ids_forn = set(compras_forn["cotacao_id"].apply(_safe_int).unique()) - {0}
                        for cot_id_chk in cot_ids_forn:
                            _tentar_encerrar_cotacao(cot_id_chk, df_compras, df_compras_dir)

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

# ── Aba: Compra Direta ─────────────────────────────────────────────────────────
with tab_direta:
    st.markdown(
        "Itens marcados como **Compra Direta** no cadastro de Produtos — comprados diretamente, "
        "sem cotação. Marque cada item como comprado para liberar o encerramento da cotação."
    )

    cd_pendente = pd.DataFrame()
    if not df_compras_dir.empty:
        cd_pendente = df_compras_dir[
            ~df_compras_dir["comprado"].apply(lambda v: str(v).strip().lower() in ("true", "1"))
        ].copy()

    if cd_pendente.empty:
        if df_compras_dir.empty:
            st.info("Nenhum item de compra direta registrado.")
        else:
            st.success("✅ Todos os itens de compra direta foram marcados como comprado.")
    else:
        unidades_cd = sorted(cd_pendente["unidade"].astype(str).unique())
        for unid_nome in unidades_cd:
            cd_unid = cd_pendente[cd_pendente["unidade"].astype(str) == unid_nome]
            cot_ids_unid = cd_unid["cotacao_id"].apply(_safe_int).unique()
            cot_labels = [cot_map.get(c, f"Cotação #{c}") for c in cot_ids_unid if c]
            cot_str = ", ".join(filter(None, cot_labels)) or "—"

            with st.expander(f"**{unid_nome}** — {len(cd_unid)} item(ns) pendente(s) | {cot_str}"):
                st.caption("Marque os itens que já foram comprados e clique em Salvar.")

                for _, cd_row in cd_unid.iterrows():
                    row_id = str(cd_row.get("id", ""))
                    pid = _safe_int(cd_row.get("produto_id", 0))
                    prod = prod_map.get(pid, {})
                    desc = str(prod.get("descricao", f"Produto {pid}"))
                    apres = str(prod.get("apresentacao", "") or "")
                    qtd = _safe_float(cd_row.get("quantidade", 0))
                    col_cb, col_info = st.columns([1, 7])
                    with col_cb:
                        st.checkbox("", key=f"cd_chk_{row_id}", value=False, label_visibility="collapsed")
                    with col_info:
                        st.markdown(f"**{desc}** — {apres} — Qtd: **{qtd:g}**")

                if st.button("💾 Marcar selecionados como comprado", key=f"cd_save_{unid_nome}", use_container_width=True):
                    ids_to_mark = [
                        str(r.get("id", ""))
                        for _, r in cd_unid.iterrows()
                        if st.session_state.get(f"cd_chk_{str(r.get('id', ''))}", False)
                    ]
                    if not ids_to_mark:
                        st.warning("Selecione pelo menos um item.")
                    else:
                        df_cd_upd = ler_df("compras_diretas")
                        for rid in ids_to_mark:
                            idx_cd = df_cd_upd[df_cd_upd["id"].astype(str) == rid].index
                            if len(idx_cd):
                                df_cd_upd.at[idx_cd[0], "comprado"] = "True"
                        escrever_df("compras_diretas", df_cd_upd)

                        # Encerra cotação se todos os pedidos e compras_diretas concluídos
                        for cot_id_chk in cot_ids_unid:
                            _tentar_encerrar_cotacao(cot_id_chk, df_compras, df_cd_upd)

                        st.cache_data.clear()
                        st.rerun()
