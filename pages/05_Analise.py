import streamlit as st
import pandas as pd
import datetime
import urllib.parse
import re
from modules.auth import requer_permissao
from modules.google_sheets import ler_df, escrever_df, get_sheet

usuario = requer_permissao("analise")

st.title("📊 Análise de Preços")

st.markdown(
    "<style>.block-container{max-width:100%!important;padding-left:1rem;padding-right:1rem}</style>",
    unsafe_allow_html=True,
)

# ── Helpers ───────────────────────────────────────────────────────────────────
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

def _preco_norm(preco, tipo, qtd_emb):
    p = _safe_float(preco)
    q = max(_safe_float(qtd_emb, 1.0), 0.001)
    return p / q if str(tipo) == "Fardo/Caixa" and q > 1 else p

def _next_id(df, col="id"):
    if df.empty or col not in df.columns:
        return 1
    try:
        return int(df[col].apply(_safe_int).max()) + 1
    except Exception:
        return 1

# ── Load data ─────────────────────────────────────────────────────────────────
df_cotacoes     = ler_df("cotacoes")
df_respostas    = ler_df("respostas")
df_produtos     = ler_df("produtos")
df_fornecedores = ler_df("fornecedores")
df_pedidos      = ler_df("pedidos")
df_itens        = ler_df("itens_pedido")
df_hist_precos  = ler_df("historico_precos")
df_unidades     = ler_df("unidades")
df_compras      = ler_df("compras")

# nome → nome_fantasia map for hotel units
_unid_fantasia = {}
unid_map = {}
if not df_unidades.empty:
    for _, _ur in df_unidades.iterrows():
        _nf = str(_ur.get("nome_fantasia", "") or "").strip()
        _nm = str(_ur.get("nome", "") or "").strip()
        if _nm:
            _unid_fantasia[_nm] = _nf if _nf else _nm
            unid_map[_nm] = dict(_ur)

def _unid_label(u: str) -> str:
    return _unid_fantasia.get(str(u), str(u))

# Mapas globais (usados nas duas tabs)
prod_map = {_safe_int(r["id"]): r for _, r in df_produtos.iterrows()} if not df_produtos.empty else {}
forn_map = {_safe_int(r["id"]): r for _, r in df_fornecedores.iterrows()} if not df_fornecedores.empty else {}

# ── Separar cotações ativas vs encerradas ────────────────────────────────────
_ids_com_resp = set()
if not df_respostas.empty:
    _ids_com_resp = set(df_respostas["cotacao_id"].apply(_safe_int).unique())

_cots_ativas = pd.DataFrame()
_cots_enc    = pd.DataFrame()
if not df_cotacoes.empty:
    _cots_ativas = df_cotacoes[
        (df_cotacoes["status"] == "aberta") &
        df_cotacoes["id"].apply(_safe_int).isin(_ids_com_resp)
    ]
    _cots_enc = df_cotacoes[
        (df_cotacoes["status"] == "encerrada") &
        df_cotacoes["id"].apply(_safe_int).isin(_ids_com_resp)
    ]

tab_ativa, tab_enc = st.tabs(["📋 Cotação Ativa", "📁 Encerradas (consulta)"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB ENCERRADAS (read-only)
# ─────────────────────────────────────────────────────────────────────────────
with tab_enc:
    if _cots_enc.empty:
        st.info("Nenhuma cotação encerrada com respostas.")
    else:
        def _label_enc(x):
            row = _cots_enc[_cots_enc["id"].apply(_safe_int) == _safe_int(x)]
            if row.empty:
                return f"Cotação #{_safe_int(x)}"
            nome = str(row.iloc[0].get("nome", "") or "").strip()
            return nome if nome else f"Cotação #{_safe_int(x)}"

        cot_enc_sel = _safe_int(st.selectbox(
            "Cotação encerrada", options=_cots_enc["id"].tolist(),
            format_func=_label_enc, key="enc_sel",
        ))

        resps_enc = (
            df_respostas[df_respostas["cotacao_id"].apply(_safe_int) == cot_enc_sel].copy()
            if not df_respostas.empty else pd.DataFrame()
        )
        if resps_enc.empty:
            st.warning("Nenhuma resposta registrada para esta cotação.")
        else:
            prod_ids_enc = sorted({_safe_int(r["produto_id"]) for _, r in resps_enc.iterrows()})
            forn_ids_enc = sorted({_safe_int(r["fornecedor_id"]) for _, r in resps_enc.iterrows()})

            st.caption("🔒 Visualização somente leitura — nenhuma informação foi alterada.")
            st.markdown("---")

            # Cabeçalho
            _cols_e = [2.5, 1.5] + [1.8] * len(forn_ids_enc)
            hdr_e = st.columns(_cols_e)
            hdr_e[0].markdown("**Produto**")
            hdr_e[1].markdown("**Qtd**")
            for _i, _fid in enumerate(forn_ids_enc):
                _fn = str(forn_map.get(_fid, {}).get("razao_social", f"#{_fid}"))
                _fn_c = (_fn[:20] + "…") if len(_fn) > 20 else _fn
                hdr_e[2 + _i].markdown(f"**{_fn_c}**")

            # Checar compras para esta cotação (para marcar vencedores)
            _compras_enc = (
                df_compras[df_compras["cotacao_id"].apply(_safe_int) == cot_enc_sel]
                if not df_compras.empty and "cotacao_id" in df_compras.columns else pd.DataFrame()
            )
            _forn_comprado = set()
            if not _compras_enc.empty:
                _forn_comprado = set(_compras_enc["fornecedor_id"].apply(_safe_int).unique())

            # Tabela de preços
            peds_enc = (
                df_pedidos[df_pedidos["cotacao_id"].apply(_safe_int) == cot_enc_sel]
                if not df_pedidos.empty and "cotacao_id" in df_pedidos.columns else pd.DataFrame()
            )
            for _pid in prod_ids_enc:
                _prod = prod_map.get(_pid, {})
                _nome_p = str(_prod.get("descricao", f"Produto {_pid}"))
                _apres  = str(_prod.get("apresentacao", ""))
                _qtd_tot = 0.0
                if not peds_enc.empty and not df_itens.empty:
                    for _, _ped in peds_enc.iterrows():
                        _it = df_itens[
                            (df_itens["pedido_id"].apply(_safe_int) == _safe_int(_ped["id"])) &
                            (df_itens["produto_id"].apply(_safe_int) == _pid)
                        ]
                        if not _it.empty:
                            _qtd_tot += _safe_float(_it.iloc[0]["quantidade"])

                _row_e = st.columns(_cols_e)
                _row_e[0].markdown(f"**{_nome_p}**")
                if _apres:
                    _row_e[0].caption(_apres)
                _row_e[1].markdown(f"{_qtd_tot:g}")

                _resps_p = {
                    _safe_int(r["fornecedor_id"]): r
                    for _, r in resps_enc[resps_enc["produto_id"].apply(_safe_int) == _pid].iterrows()
                }
                _precos_p = [(fid, _preco_norm(r["preco"], r.get("tipo_embalagem",""), r.get("qtd_por_embalagem",1)))
                             for fid, r in _resps_p.items()]
                _melhor_fid = min(_precos_p, key=lambda x: x[1])[0] if _precos_p else None

                for _i, _fid in enumerate(forn_ids_enc):
                    with _row_e[2 + _i]:
                        if _fid not in _resps_p:
                            st.caption("—")
                            continue
                        _r = _resps_p[_fid]
                        _pn = _preco_norm(_r["preco"], _r.get("tipo_embalagem",""), _r.get("qtd_por_embalagem",1))
                        _comprou = _fid in _forn_comprado
                        _is_best = _fid == _melhor_fid
                        if _comprou:
                            _bg = "background:#dbeafe;border:2px solid #3b82f6;border-radius:6px;padding:5px"
                            _badge = "<br><small style='color:#1d4ed8'>✓ Comprado</small>"
                        elif _is_best:
                            _bg = "background:#dcfce7;border:1px solid #86efac;border-radius:6px;padding:5px"
                            _badge = "<br><small style='color:#15803d'>★ Melhor</small>"
                        else:
                            _bg = "border:1px solid #e5e7eb;border-radius:6px;padding:5px"
                            _badge = ""
                        st.markdown(
                            f"<div style='{_bg}'><b>R$ {_pn:.2f}</b>{_badge}</div>",
                            unsafe_allow_html=True,
                        )
                        if str(_r.get("marca","")).strip():
                            st.caption(f"🏷️ {str(_r['marca'])[:20]}")

                st.markdown("<hr style='margin:4px 0'>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB ATIVA
# ─────────────────────────────────────────────────────────────────────────────
cotacao_sel = None  # será definido dentro da tab ativa
with tab_ativa:
    if _cots_ativas.empty:
        st.info("Nenhuma cotação ativa com respostas disponível para análise.")
    else:
        cotacoes_com_resp = _cots_ativas

        def _label_cot(x):
            row = cotacoes_com_resp[cotacoes_com_resp["id"].apply(_safe_int) == _safe_int(x)]
            if row.empty:
                return f"Cotação #{_safe_int(x)}"
            nome = str(row.iloc[0].get("nome", "") or "").strip()
            return nome if nome else f"Cotação #{_safe_int(x)}"

        cotacao_sel = _safe_int(st.selectbox(
            "Cotação", options=cotacoes_com_resp["id"].tolist(), format_func=_label_cot,
        ))

if cotacao_sel is None:
    st.stop()

# Nome da cotação selecionada (para PDF e nome de arquivo)
_cot_row = cotacoes_com_resp[cotacoes_com_resp["id"].apply(_safe_int) == cotacao_sel]
nome_cot = str(_cot_row.iloc[0].get("nome", "") or "").strip() if not _cot_row.empty else ""
nome_cot_label = nome_cot if nome_cot else f"Cotação #{cotacao_sel}"

# ── Build data for this cotação ───────────────────────────────────────────────
respostas = (
    df_respostas[df_respostas["cotacao_id"].apply(_safe_int) == cotacao_sel].copy()
    if not df_respostas.empty else pd.DataFrame()
)
if respostas.empty:
    st.warning("Nenhuma resposta de fornecedor para esta cotação.")
    st.stop()

forn_ids = sorted({_safe_int(r["fornecedor_id"]) for _, r in respostas.iterrows()})
prod_ids = sorted({_safe_int(r["produto_id"]) for _, r in respostas.iterrows()})

# Responses: (prod_id, forn_id) → data
resp_dict = {}
for _, r in respostas.iterrows():
    pid = _safe_int(r["produto_id"])
    fid = _safe_int(r["fornecedor_id"])
    pn  = _preco_norm(r["preco"], r.get("tipo_embalagem", ""), r.get("qtd_por_embalagem", 1))
    resp_dict[(pid, fid)] = {
        "preco":      _safe_float(r["preco"]),
        "preco_norm": pn,
        "tipo":       str(r.get("tipo_embalagem", "")),
        "qtd_emb":    _safe_float(r.get("qtd_por_embalagem", 1), 1.0),
        "obs":        str(r.get("observacao", "")),
        "marca":      str(r.get("marca", "")),
    }

# Best price per product
melhor_preco = {}
for pid in prod_ids:
    cands = [(fid, resp_dict[(pid, fid)]["preco_norm"])
             for fid in forn_ids if (pid, fid) in resp_dict]
    if cands:
        melhor_preco[pid] = min(cands, key=lambda x: x[1])

# Pedidos and units for this cotação
peds_cot = (
    df_pedidos[df_pedidos["cotacao_id"].apply(_safe_int) == cotacao_sel]
    if not df_pedidos.empty and "cotacao_id" in df_pedidos.columns else pd.DataFrame()
)
unidades_cot = sorted(peds_cot["unidade"].unique().tolist()) if not peds_cot.empty else []

# Original quantities per product per unit (from itens_pedido)
def _qtd_orig(pid, unid):
    if df_itens.empty or peds_cot.empty:
        return 0.0
    total = 0.0
    for _, ped in peds_cot[peds_cot["unidade"] == unid].iterrows():
        ped_id = _safe_int(ped["id"])
        item = df_itens[
            (df_itens["pedido_id"].apply(_safe_int) == ped_id) &
            (df_itens["produto_id"].apply(_safe_int) == pid)
        ]
        if not item.empty:
            total += _safe_float(item.iloc[0]["quantidade"])
    return total

# Historical prices (last 3 won purchases per product)
def _historico(pid):
    if df_hist_precos.empty:
        return []
    hist = df_hist_precos[
        (df_hist_precos["produto_id"].apply(_safe_int) == pid) &
        (df_hist_precos["ganhou"] == True)
    ].copy()
    if hist.empty:
        return []
    hist = hist.sort_values("data", ascending=False).head(3)
    result = []
    for _, h in hist.iterrows():
        fid  = _safe_int(h["fornecedor_id"])
        nome = str(forn_map.get(fid, {}).get("razao_social", f"#{fid}"))
        pn   = _safe_float(h.get("preco_normalizado", h.get("preco", 0)))
        result.append({"data": str(h.get("data", ""))[:10], "preco": pn, "fornecedor": nome})
    return result

# ── Session state ─────────────────────────────────────────────────────────────
sk = f"analise_{cotacao_sel}"

# Promover resultado pendente para estado exibível (após rerun)
_compra_pending = st.session_state.pop(f"{sk}_compra_pending", None)
if _compra_pending is not None:
    st.session_state[f"{sk}_compra_done_{_compra_pending}"] = True

# Inicializar compra_done a partir do banco (persiste refreshes e cache clears)
if not df_compras.empty:
    _compras_cot = df_compras[
        (df_compras["cotacao_id"].apply(_safe_int) == cotacao_sel) &
        (df_compras["pedido_gerado"].astype(str).str.lower().isin(["false", "0", ""]))
    ]
    for _fid_db in _compras_cot["fornecedor_id"].apply(_safe_int).unique():
        _key_db = f"{sk}_compra_done_{_fid_db}"
        if _key_db not in st.session_state:
            st.session_state[_key_db] = True

if f"{sk}_init" not in st.session_state:
    for pid in prod_ids:
        skey = f"{sk}_sel_{pid}"
        if skey not in st.session_state and pid in melhor_preco:
            st.session_state[skey] = melhor_preco[pid][0]
    for pid in prod_ids:
        for unid in unidades_cot:
            qkey = f"{sk}_qtd_{pid}_{unid}"
            if qkey not in st.session_state:
                st.session_state[qkey] = _qtd_orig(pid, unid)
    st.session_state[f"{sk}_init"] = True

def _get_sel(pid):
    return st.session_state.get(f"{sk}_sel_{pid}")

def _get_qtd(pid, unid):
    return _safe_float(st.session_state.get(f"{sk}_qtd_{pid}_{unid}", _qtd_orig(pid, unid)))

def _calc_totais():
    totais = {fid: {u: 0.0 for u in unidades_cot} for fid in forn_ids}
    for pid in prod_ids:
        sel = _get_sel(pid)
        if sel is None or (pid, sel) not in resp_dict:
            continue
        pn = resp_dict[(pid, sel)]["preco_norm"]
        for unid in unidades_cot:
            totais[sel][unid] += _get_qtd(pid, unid) * pn
    return totais

# ── Action buttons ────────────────────────────────────────────────────────────
col_a, col_b, _ = st.columns([2, 2, 6])
with col_a:
    if st.button("⭐ Selecionar melhores preços", use_container_width=True):
        for pid in prod_ids:
            if pid in melhor_preco:
                st.session_state[f"{sk}_sel_{pid}"] = melhor_preco[pid][0]
        st.rerun()
with col_b:
    if st.button("🗑️ Limpar seleções", use_container_width=True):
        for pid in prod_ids:
            st.session_state.pop(f"{sk}_sel_{pid}", None)
        st.rerun()

st.markdown("---")

# ── GRID ──────────────────────────────────────────────────────────────────────
W_PROD, W_QTD, W_HIST, W_FORN = 2.5, 1.3, 1.5, 1.6
col_widths = [W_PROD, W_QTD, W_HIST] + [W_FORN] * len(forn_ids)

# Header
hdr = st.columns(col_widths)
hdr[0].markdown("**Produto**")
hdr[1].markdown("**Quantidade**")
hdr[2].markdown("**Última Compra**")
for i, fid in enumerate(forn_ids):
    nome = str(forn_map.get(fid, {}).get("razao_social", f"#{fid}"))
    nome_c   = (nome[:22] + "…") if len(nome) > 22 else nome
    ped_min  = _safe_float(forn_map.get(fid, {}).get("pedido_minimo", 0))
    min_txt  = f"*Mín: R$ {ped_min:.0f}*" if ped_min > 0 else ""
    hdr[3 + i].markdown(f"**{nome_c}**  \n{min_txt}")

st.markdown("<hr style='margin:2px 0 8px'>", unsafe_allow_html=True)

# Product rows
for pid in prod_ids:
    prod      = prod_map.get(pid, {})
    nome_prod = str(prod.get("descricao", f"Produto {pid}"))
    ub        = str(prod.get("unidade_base", ""))
    apres     = str(prod.get("apresentacao", ""))
    hist      = _historico(pid)
    qtds_unid = {u: _get_qtd(pid, u) for u in unidades_cot}
    qtd_total = sum(qtds_unid.values())
    cur_sel   = _get_sel(pid)

    row = st.columns(col_widths)

    with row[0]:
        st.markdown(f"**{nome_prod}**")
        if apres:
            st.caption(apres)

    with row[1]:
        st.markdown(f"**{qtd_total:.1f}**")
        qtds_pos = {u: q for u, q in qtds_unid.items() if q > 0}
        if len(qtds_pos) > 1:
            with st.expander("▸ por hotel"):
                for u, q in qtds_pos.items():
                    st.caption(f"{_unid_label(u)}: {q:.1f}")

    with row[2]:
        if hist:
            h0 = hist[0]
            st.markdown(f"R$ {h0['preco']:.2f}")
            st.caption(f"{h0['data']}  \n{h0['fornecedor'][:14]}")
            if len(hist) > 1:
                with st.expander("▸ histórico"):
                    for h in hist:
                        st.caption(f"{h['data']}: R$ {h['preco']:.2f}  \n{h['fornecedor'][:18]}")
        else:
            st.caption("Sem histórico")

    for i, fid in enumerate(forn_ids):
        with row[3 + i]:
            if (pid, fid) not in resp_dict:
                st.markdown(
                    "<span style='color:#bbb;font-size:0.85em'>Não possui</span>",
                    unsafe_allow_html=True,
                )
                continue

            rd      = resp_dict[(pid, fid)]
            pn      = rd["preco_norm"]
            is_best = pid in melhor_preco and melhor_preco[pid][0] == fid
            is_sel  = cur_sel == fid

            if is_sel:
                bg    = "background:#dbeafe;border:2px solid #3b82f6;border-radius:6px;padding:6px;margin-bottom:4px"
                badge = "<br><small style='color:#1d4ed8'>✓ Selecionado</small>"
            elif is_best:
                bg    = "background:#dcfce7;border:1px solid #86efac;border-radius:6px;padding:6px;margin-bottom:4px"
                badge = "<br><small style='color:#15803d'>★ Melhor Preço</small>"
            else:
                bg    = "border:1px solid #e5e7eb;border-radius:6px;padding:6px;margin-bottom:4px"
                badge = ""

            st.markdown(
                f"<div style='{bg}'><b>R$ {pn:.2f}</b>{badge}</div>",
                unsafe_allow_html=True,
            )
            if rd["marca"]:
                st.caption(f"🏷️ {rd['marca'][:25]}")
            if rd["obs"]:
                st.caption(rd["obs"][:30])

            if not is_sel:
                if st.button("Selecionar", key=f"{sk}_s_{pid}_{fid}",
                             use_container_width=True, type="secondary"):
                    st.session_state[f"{sk}_sel_{pid}"] = fid
                    st.rerun()
            else:
                if st.button("Remover", key=f"{sk}_r_{pid}_{fid}",
                             use_container_width=True):
                    st.session_state.pop(f"{sk}_sel_{pid}", None)
                    st.rerun()

    st.markdown("<hr style='margin:4px 0'>", unsafe_allow_html=True)


# ── Save adjusted quantities to DB ───────────────────────────────────────────
def _salvar_quantidades():
    df_itens_upd = ler_df("itens_pedido").copy()
    next_id = _next_id(df_itens_upd) if not df_itens_upd.empty else 1
    cols = list(df_itens_upd.columns) if not df_itens_upd.empty else ["id", "pedido_id", "produto_id", "quantidade"]
    for pid in prod_ids:
        for unid in unidades_cot:
            nova_qtd = _get_qtd(pid, unid)
            peds_unid = peds_cot[peds_cot["unidade"] == unid] if not peds_cot.empty else pd.DataFrame()
            for _, ped in peds_unid.iterrows():
                ped_id = _safe_int(ped["id"])
                if not df_itens_upd.empty:
                    mask = (
                        (df_itens_upd["pedido_id"].apply(_safe_int) == ped_id) &
                        (df_itens_upd["produto_id"].apply(_safe_int) == pid)
                    )
                else:
                    mask = pd.Series([], dtype=bool)
                if not df_itens_upd.empty and mask.any():
                    df_itens_upd.loc[mask, "quantidade"] = str(nova_qtd)
                elif nova_qtd > 0:
                    new_row = {col: "" for col in cols}
                    new_row["id"] = str(next_id)
                    new_row["pedido_id"] = str(ped_id)
                    new_row["produto_id"] = str(pid)
                    new_row["quantidade"] = str(nova_qtd)
                    df_itens_upd = pd.concat([df_itens_upd, pd.DataFrame([new_row])], ignore_index=True)
                    next_id += 1
    try:
        escrever_df("itens_pedido", df_itens_upd)
        return True, None
    except Exception as e:
        return False, str(e)


# ── Helpers PDF / WhatsApp ────────────────────────────────────────────────────
_CSS_PDF = """<style>
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
.section{margin-bottom:20px;page-break-after:always}
.section:last-child{page-break-after:auto}
@media print{.no-print{display:none!important}}
</style>"""


def _addr_u(r):
    parts = [
        str(r.get("logradouro", "") or ""),
        str(r.get("numero", "") or ""),
        str(r.get("complemento", "") or ""),
        str(r.get("bairro", "") or ""),
        (str(r.get("cidade", "") or "") +
         ((" - " + str(r.get("estado", "") or "")) if r.get("estado") else "")),
    ]
    return ", ".join(p for p in parts if p.strip())


def _html_pedido_forn(fid):
    forn = forn_map.get(fid, {})
    forn_min = _safe_float(forn.get("pedido_minimo", 0))
    forn_min_str = f"R$ {forn_min:.2f}" if forn_min > 0 else "—"
    prods_sel = [pid for pid in prod_ids if _get_sel(pid) == fid]
    secoes = []
    grand_total = 0.0
    idx = 1
    for unid in unidades_cot:
        itens_det = []
        for pid in prods_sel:
            qty = _get_qtd(pid, unid)
            if qty <= 0:
                continue
            rd   = resp_dict.get((pid, fid), {})
            prod = prod_map.get(pid, {})
            _qtd_emb = rd.get("qtd_emb", 1.0)
            _gram_inf = str(rd.get("tipo", ""))
            if _qtd_emb and float(_qtd_emb) > 1:
                _gram_inf = f"{_gram_inf} x{float(_qtd_emb):g}"
            itens_det.append({
                "codigo":    str(prod.get("codigo", "") or "—"),
                "descricao": str(prod.get("descricao", f"Produto {pid}")),
                "gram_sol":  str(prod.get("apresentacao", "") or ""),
                "obs":       str(rd.get("obs", "")),
                "marca":     str(rd.get("marca", "")),
                "gram_inf":  _gram_inf.strip(),
                "preco":     rd.get("preco_norm", 0.0),
                "qtd":       qty,
            })
        if not itens_det:
            continue
        unid_info = unid_map.get(str(unid), {"nome": unid, "nome_fantasia": unid})
        total = sum(_safe_float(i["preco"]) * _safe_float(i["qtd"]) for i in itens_det)
        grand_total += total
        thead = (
            "<thead><tr><th>Código</th><th>Produto</th><th>Gram. Solicitada</th>"
            "<th>Marca</th><th>Obs</th><th>Gram. Informada</th>"
            "<th>Preço Un.</th><th>Qtde.</th><th>Total</th></tr></thead>"
        )
        rows = ""
        for it in itens_det:
            obs_cell = it["obs"] if it["obs"] else "—"
            p, q = _safe_float(it["preco"]), _safe_float(it["qtd"])
            rows += (
                f"<tr><td>{it['codigo']}</td><td>{it['descricao']}</td>"
                f"<td>{it['gram_sol']}</td>"
                f"<td>{it['marca']}</td>"
                f"<td style='font-size:10px'>{obs_cell}</td>"
                f"<td>{it['gram_inf']}</td>"
                f"<td>R$ {p:.2f}</td><td>{q:g}</td>"
                f"<td>R$ {p*q:.2f}</td></tr>"
            )
        secoes.append(f"""<div class="section">
  <h2>Pedido nº {idx} | Cotação: {nome_cot_label} | Data: {datetime.date.today().strftime('%d/%m/%Y')}</h2>
  <p class="status">Status do pedido: Pedido realizado - aguardando fornecedor</p>
  <h3>Comprador</h3>
  <div class="grid2">
    <div><b>Razão Social:</b> {unid_info.get('nome','')}<br>
    <b>Nome Fantasia:</b> {unid_info.get('nome_fantasia','')}<br>
    <b>CNPJ:</b> {unid_info.get('cnpj','')}</div>
    <div><b>Endereço:</b> {_addr_u(unid_info)}</div>
  </div>
  <h3>Fornecedor</h3>
  <div class="grid2">
    <div><b>Razão Social:</b> {forn.get('razao_social','')}<br>
    <b>Nome Fantasia:</b> {forn.get('nome_fantasia','')}<br>
    <b>CNPJ:</b> {forn.get('cnpj','')}<br>
    <b>Observação do Fornecedor:</b></div>
    <div><b>Telefone:</b> {forn.get('telefone','')}<br>
    <b>Prazo para pagamento:</b><br><b>Dias de entrega:</b><br>
    <b>Pedido mínimo:</b> {forn_min_str}</div>
  </div>
  <h3>Itens do Pedido</h3>
  <table>{thead}<tbody>{rows}</tbody></table>
  <p><b>Comentários Gerais:</b> Pedido criado automaticamente pelo sistema de cotação</p>
  <p class="total">Total do Pedido: R$ {total:.2f}</p>
</div>""")
        idx += 1
    total_geral_html = (
        f"<div style='margin-top:24px;padding:12px 0;border-top:2px solid #333;text-align:right'>"
        f"<b style='font-size:14px'>Total Geral do Fornecedor: R$ {grand_total:.2f}</b></div>"
    )
    return _CSS_PDF + "<body>" + "".join(secoes) + total_geral_html + "</body>"


def _wa_link_forn(fid):
    forn = forn_map.get(fid, {})
    tel_raw = str(forn.get("whatsapp", "") or forn.get("telefone", "") or "")
    tel = re.sub(r"[^\d]", "", tel_raw)
    if tel and not tel.startswith("55"):
        tel = "55" + tel
    prods_sel = [pid for pid in prod_ids if _get_sel(pid) == fid]
    nome_forn = str(forn.get("razao_social", f"#{fid}"))
    lines = [
        "*Pedido de Compra*",
        f"Data: {datetime.date.today().strftime('%d/%m/%Y')}",
        f"Fornecedor: {nome_forn}",
    ]
    grand_total = 0.0
    for unid in unidades_cot:
        itens = [
            (pid, _get_qtd(pid, unid), resp_dict.get((pid, fid), {}).get("preco_norm", 0))
            for pid in prods_sel if _get_qtd(pid, unid) > 0
        ]
        if not itens:
            continue
        total_unid = sum(q * p for _, q, p in itens)
        grand_total += total_unid
        lines.append(f"\n*{_unid_label(unid)}*")
        for pid, q, p in itens:
            nome_p = str(prod_map.get(pid, {}).get("descricao", f"Produto {pid}"))
            lines.append(f"• {nome_p}: {q:g} x R$ {p:.2f} = R$ {q*p:.2f}")
        lines.append(f"Subtotal: R$ {total_unid:.2f}")
    lines.append(f"\n*Total Geral: R$ {grand_total:.2f}*")
    msg = "\n".join(lines)
    base = f"https://wa.me/{tel}" if tel else "https://wa.me/"
    return base + "?text=" + urllib.parse.quote(msg)


# ── FOOTER: resumo por fornecedor ─────────────────────────────────────────────
st.markdown("## Resumo por Fornecedor")

totais = _calc_totais()

if not forn_ids:
    st.stop()

# Horizontal scroll when many suppliers
st.markdown(
    "<style>"
    "[data-testid='stHorizontalBlock'].forn-footer "
    "{ overflow-x: auto !important; flex-wrap: nowrap !important; }"
    "[data-testid='stHorizontalBlock'].forn-footer > [data-testid='stColumn'] "
    "{ min-width: 160px !important; }"
    "</style>",
    unsafe_allow_html=True,
)

foot_cols = st.columns(len(forn_ids))

for i, fid in enumerate(forn_ids):
    forn     = forn_map.get(fid, {})
    nome     = str(forn.get("razao_social", f"#{fid}"))
    nome_c   = (nome[:22] + "…") if len(nome) > 22 else nome
    ped_min  = _safe_float(forn.get("pedido_minimo", 0))
    tot_geral = sum(totais[fid].values())

    with foot_cols[i]:
        st.markdown(f"**{nome_c}**")

        if tot_geral == 0:
            st.caption("Nenhum item selecionado")
        else:
            st.markdown(f"**R$ {tot_geral:.2f}**")

        # Por-unit minimum check
        avisos = []
        if ped_min > 0:
            for unid in unidades_cot:
                t = totais[fid][unid]
                if 0 < t < ped_min:
                    avisos.append((unid, ped_min - t))

        if avisos:
            n_avisos = len(avisos)
            with st.expander(f"⚠️ {n_avisos} aviso(s) de mínimo"):
                for u, f in avisos:
                    st.caption(f"⚠️ {_unid_label(u)}: faltam R$ {f:.2f}")
            ignorar = st.checkbox("Ignorar pedido mínimo", key=f"{sk}_ign_{fid}")
        else:
            if tot_geral > 0 and ped_min > 0:
                st.caption("✅ Mín. atingido")
            ignorar = True

        pode_comprar = tot_geral > 0 and (not avisos or ignorar)

        if st.session_state.get(f"{sk}_compra_done_{fid}"):
            nome_forn_r = str(forn_map.get(fid, {}).get("razao_social", f"#{fid}"))
            st.success(f"✅ Compra gerada para **{nome_forn_r}**!")
            nome_safe = re.sub(r"[^\w]", "_", nome_forn_r)[:30]
            cot_safe = re.sub(r"[^\w]", "_", nome_cot)[:20] if nome_cot else f"cot{cotacao_sel}"
            st.download_button(
                "⬇️ Gerar PDF",
                data=_html_pedido_forn(fid).encode("utf-8"),
                file_name=f"{nome_safe}_{cot_safe}_{datetime.date.today()}.html",
                mime="text/html",
                use_container_width=True,
                key=f"{sk}_pdf_{fid}",
            )
            _unlock_key = f"{sk}_unlock_{fid}"
            if not st.session_state.get(_unlock_key):
                if st.button("🔓 Liberar para nova compra", key=f"{sk}_ok_{fid}", use_container_width=True):
                    st.session_state[_unlock_key] = True
                    st.rerun()
            else:
                st.warning("Digite sua senha para confirmar a liberação:")
                from modules.auth import hash_senha as _hash_senha
                senha_conf = st.text_input("Senha", type="password", key=f"{sk}_pwd_{fid}", label_visibility="collapsed")
                col_conf, col_cancel = st.columns(2)
                with col_conf:
                    if st.button("Confirmar", key=f"{sk}_pwdok_{fid}", use_container_width=True, type="primary"):
                        if _hash_senha(senha_conf) == st.session_state["usuario"]["senha_hash"]:
                            # Exclui compras anteriores deste fornecedor nesta cotação
                            # para evitar duplicatas na Ordem de Compra
                            _df_itens_compra = ler_df("itens_compra")
                            _mask = (
                                (df_compras["cotacao_id"].apply(_safe_int) == cotacao_sel) &
                                (df_compras["fornecedor_id"].apply(_safe_int) == fid) &
                                (df_compras["pedido_gerado"].astype(str).str.lower().isin(["false", "0", ""]))
                            )
                            _cids_excluir = df_compras[_mask]["id"].apply(_safe_int).tolist()
                            if _cids_excluir:
                                df_compras_upd = df_compras[~df_compras["id"].apply(_safe_int).isin(_cids_excluir)].reset_index(drop=True)
                                df_itens_upd   = _df_itens_compra[~_df_itens_compra["compra_id"].apply(_safe_int).isin(_cids_excluir)].reset_index(drop=True)
                                escrever_df("compras", df_compras_upd)
                                escrever_df("itens_compra", df_itens_upd)
                            st.session_state.pop(f"{sk}_compra_done_{fid}", None)
                            st.session_state.pop(_unlock_key, None)
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Senha incorreta.")
                with col_cancel:
                    if st.button("Cancelar", key=f"{sk}_pwdcanc_{fid}", use_container_width=True):
                        st.session_state.pop(_unlock_key, None)
                        st.rerun()
        else:
            if tot_geral == 0:
                st.caption("⚠️ Selecione produtos na grade acima.")
            elif avisos and not ignorar:
                st.caption("⚠️ Marque Ignorar para prosseguir.")

            if st.button("🛒 Comprar", key=f"{sk}_cpr_{fid}",
                         use_container_width=True, type="primary"):
                if tot_geral == 0:
                    st.toast("Nenhum produto selecionado para este fornecedor. Use os botões 'Selecionar' na grade ou 'Selecionar melhores preços'.", icon="⚠️")
                elif not pode_comprar:
                    st.toast("Marque ✅ Ignorar para prosseguir mesmo sem atingir o pedido mínimo.", icon="⚠️")
                else:
                    st.session_state[f"{sk}_comprar_fid"] = fid

        # Ajuste de quantidades — sempre disponível
        compra_feita = bool(st.session_state.get(f"{sk}_compra_done_{fid}"))
        with st.expander("📦 Ajustar qtd."):
            prods_fid = [pid for pid in prod_ids if _get_sel(pid) == fid]
            if not prods_fid:
                st.caption("Nenhum produto selecionado para este fornecedor.")
            else:
                if compra_feita:
                    st.caption("🔒 Compra já gerada — quantidades bloqueadas.")

                adj_h = st.columns([2] + [1] * len(unidades_cot))
                adj_h[0].markdown("**Produto**")
                for j, u in enumerate(unidades_cot):
                    adj_h[j + 1].markdown(f"**{_unid_label(u)}**")

                for pid in prods_fid:
                    prod   = prod_map.get(pid, {})
                    nome_p = str(prod.get("descricao", f"#{pid}"))
                    ub_p   = str(prod.get("unidade_base", ""))
                    adj_r  = st.columns([2] + [1] * len(unidades_cot))
                    adj_r[0].markdown(nome_p[:22])
                    adj_r[0].caption(ub_p)
                    for j, unid in enumerate(unidades_cot):
                        qkey = f"{sk}_qtd_{pid}_{unid}"
                        if qkey not in st.session_state:
                            st.session_state[qkey] = _qtd_orig(pid, unid)
                        adj_r[j + 1].number_input(
                            "", min_value=0.0, step=0.5,
                            key=qkey, label_visibility="collapsed",
                            disabled=compra_feita,
                        )

                # Subtotais por unidade
                st.markdown("---")
                sub_h = st.columns([2] + [1] * len(unidades_cot))
                sub_h[0].markdown("**Subtotal**")
                tot_now = _calc_totais()
                for j, unid in enumerate(unidades_cot):
                    t  = tot_now[fid][unid]
                    ok = ped_min == 0 or t == 0 or t >= ped_min
                    color = "#15803d" if ok else "#b45309"
                    sub_h[j + 1].markdown(
                        f"<span style='color:{color}'><b>R$ {t:.2f}</b></span>",
                        unsafe_allow_html=True,
                    )

                if st.button("💾 Salvar quantidades", key=f"{sk}_save_{fid}",
                             use_container_width=True, disabled=compra_feita):
                    ok2, err2 = _salvar_quantidades()
                    if ok2:
                        st.toast("✅ Quantidades salvas!", icon="💾")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.toast(f"Erro ao salvar: {err2}", icon="❌")

# ── Process purchase ──────────────────────────────────────────────────────────
comprar_fid = st.session_state.pop(f"{sk}_comprar_fid", None)
if comprar_fid is not None:
    df_compras      = ler_df("compras")
    df_itens_compra = ler_df("itens_compra")
    df_hist         = ler_df("historico_precos")

    compra_id = _next_id(df_compras)
    item_id   = _next_id(df_itens_compra)
    hist_id   = _next_id(df_hist)

    prods_fid      = [pid for pid in prod_ids if _get_sel(pid) == comprar_fid]
    linhas_compras = []
    linhas_itens   = []
    linhas_hist    = []

    for unid in unidades_cot:
        valor_unid = sum(
            _get_qtd(pid, unid) * resp_dict[(pid, comprar_fid)]["preco_norm"]
            for pid in prods_fid
            if (pid, comprar_fid) in resp_dict and _get_qtd(pid, unid) > 0
        )
        if valor_unid == 0:
            continue
        linhas_compras.append([
            compra_id, cotacao_sel, comprar_fid,
            datetime.date.today().isoformat(),
            round(valor_unid, 2), False, "", "", "", unid,
        ])
        for pid in prods_fid:
            if (pid, comprar_fid) not in resp_dict:
                continue
            qty = _get_qtd(pid, unid)
            if qty <= 0:
                continue
            rd = resp_dict[(pid, comprar_fid)]
            linhas_itens.append([
                item_id, compra_id, pid,
                qty, rd["preco"], rd["preco_norm"], rd["qtd_emb"],
            ])
            item_id += 1
        compra_id += 1

    # History for all products this supplier won
    for pid in prods_fid:
        sel_fid   = _get_sel(pid)
        resps_pid = respostas[respostas["produto_id"].apply(_safe_int) == pid]
        for _, rr in resps_pid.iterrows():
            rfid   = _safe_int(rr["fornecedor_id"])
            ganhou = rfid == sel_fid
            linhas_hist.append([
                hist_id, pid, rfid, cotacao_sel,
                _safe_float(rr["preco"]),
                str(rr.get("tipo_embalagem", "")),
                _safe_float(rr.get("qtd_por_embalagem", 1), 1.0),
                round(_preco_norm(rr["preco"], rr.get("tipo_embalagem",""), rr.get("qtd_por_embalagem",1)), 4),
                ganhou,
                datetime.date.today().isoformat(),
            ])
            hist_id += 1

    if not linhas_compras:
        st.toast(
            "Nenhum item com quantidade > 0 encontrado. Verifique as seleções e quantidades.",
            icon="⚠️",
        )
    else:
        try:
            get_sheet("compras").append_rows(linhas_compras)
            if linhas_itens:
                get_sheet("itens_compra").append_rows(linhas_itens)
            if linhas_hist:
                get_sheet("historico_precos").append_rows(linhas_hist)
            st.session_state[f"{sk}_compra_pending"] = comprar_fid
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.toast(f"Erro ao salvar compra: {e}", icon="❌")
