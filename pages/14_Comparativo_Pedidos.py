import re
import streamlit as st
import pandas as pd
from modules.auth import requer_permissao
from modules.google_sheets import ler_df

usuario = requer_permissao("comparativo_pedidos")

st.title("📋 Comparativo de Pedidos")
st.caption("Comparativo entre o que foi solicitado pelos hotéis e o que foi efetivamente comprado.")


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


@st.cache_data(ttl=300)
def _carregar_dados():
    return {
        "cotacoes":       ler_df("cotacoes"),
        "pedidos":        ler_df("pedidos"),
        "itens_pedido":   ler_df("itens_pedido"),
        "produtos":       ler_df("produtos"),
        "unidades":       ler_df("unidades"),
        "compras":        ler_df("compras"),
        "itens_compra":   ler_df("itens_compra"),
        "compras_diretas": ler_df("compras_diretas"),
    }


dados = _carregar_dados()
df_cotacoes       = dados["cotacoes"]
df_pedidos        = dados["pedidos"]
df_itens_pedido   = dados["itens_pedido"]
df_produtos       = dados["produtos"]
df_unidades       = dados["unidades"]
df_compras        = dados["compras"]
df_itens_compra   = dados["itens_compra"]
df_compras_dir    = dados["compras_diretas"]

# Maps
prod_map = {_safe_int(r["id"]): r for _, r in df_produtos.iterrows()} if not df_produtos.empty else {}
unid_fantasia = {}
if not df_unidades.empty:
    for _, ur in df_unidades.iterrows():
        nm = str(ur.get("nome", "") or "").strip()
        nf = str(ur.get("nome_fantasia", "") or "").strip()
        if nm:
            unid_fantasia[nm] = nf if nf else nm


def _unid_label(u: str) -> str:
    return unid_fantasia.get(str(u), str(u))


# ── Seleção de cotação ────────────────────────────────────────────────────────
if df_cotacoes.empty:
    st.info("Nenhuma cotação registrada.")
    st.stop()

cot_ids = sorted(df_cotacoes["id"].apply(_safe_int).tolist(), reverse=True)


def _label_cot(x):
    row = df_cotacoes[df_cotacoes["id"].apply(_safe_int) == _safe_int(x)]
    if row.empty:
        return f"Cotação #{x}"
    nome = str(row.iloc[0].get("nome", "") or "").strip()
    data = str(row.iloc[0].get("data_criacao", "") or "").strip()[:10]
    label = nome if nome else f"Cotação #{x}"
    return f"{label}  ({data})" if data else label


cotacao_sel = _safe_int(st.selectbox("Cotação", options=cot_ids, format_func=_label_cot))

# ── Nota do responsável ───────────────────────────────────────────────────────
nota = ""
if "observacoes_compra" in df_cotacoes.columns:
    cot_row = df_cotacoes[df_cotacoes["id"].apply(_safe_int) == cotacao_sel]
    if not cot_row.empty:
        nota = str(cot_row.iloc[0].get("observacoes_compra", "") or "").strip()

# ── Filtrar dados da cotação ──────────────────────────────────────────────────
pedidos_cot = (
    df_pedidos[df_pedidos["cotacao_id"].apply(_safe_int) == cotacao_sel]
    if not df_pedidos.empty and "cotacao_id" in df_pedidos.columns
    else pd.DataFrame()
)

compras_cot = (
    df_compras[df_compras["cotacao_id"].apply(_safe_int) == cotacao_sel]
    if not df_compras.empty and "cotacao_id" in df_compras.columns
    else pd.DataFrame()
)

comp_ids = set(compras_cot["id"].apply(_safe_int).tolist()) if not compras_cot.empty else set()
itens_comp_cot = (
    df_itens_compra[df_itens_compra["compra_id"].apply(_safe_int).isin(comp_ids)]
    if not df_itens_compra.empty and comp_ids
    else pd.DataFrame()
)

cd_cot = (
    df_compras_dir[
        (df_compras_dir["cotacao_id"].apply(_safe_int) == cotacao_sel) &
        (df_compras_dir["comprado"].astype(str).str.lower().isin(["true", "1"]))
    ]
    if not df_compras_dir.empty and "cotacao_id" in df_compras_dir.columns
    else pd.DataFrame()
)

unidades_cot = sorted(pedidos_cot["unidade"].unique().tolist()) if not pedidos_cot.empty else []

if not unidades_cot:
    st.info("Nenhum pedido registrado para esta cotação.")
    st.stop()

# ── Construir dados por hotel ─────────────────────────────────────────────────
hotel_data = {}
all_discrepancias = []
all_prod_hoteis = []

for unidade in unidades_cot:
    label = _unid_label(unidade)

    # Solicitado (usa qtd_original se disponível — preserva quantidades antes de ajustes do comprador)
    sol = {}
    peds_h = pedidos_cot[pedidos_cot["unidade"].astype(str) == str(unidade)]
    for _, ped in peds_h.iterrows():
        if df_itens_pedido.empty:
            continue
        itens = df_itens_pedido[df_itens_pedido["pedido_id"].apply(_safe_int) == _safe_int(ped["id"])]
        for _, item in itens.iterrows():
            pid = _safe_int(item["produto_id"])
            if "qtd_original" in df_itens_pedido.columns:
                qtd_orig = str(item.get("qtd_original", "") or "").strip()
                qtd = _safe_float(qtd_orig) if qtd_orig not in ("", "nan") else _safe_float(item["quantidade"])
            else:
                qtd = _safe_float(item["quantidade"])
            sol[pid] = sol.get(pid, 0) + qtd

    # Comprado via cotação
    comp = {}
    if not compras_cot.empty:
        comp_h = compras_cot[compras_cot["unidade"].astype(str) == str(unidade)]
        for _, c in comp_h.iterrows():
            cid = _safe_int(c["id"])
            if not itens_comp_cot.empty:
                itens = itens_comp_cot[itens_comp_cot["compra_id"].apply(_safe_int) == cid]
                for _, ic in itens.iterrows():
                    pid = _safe_int(ic["produto_id"])
                    comp[pid] = comp.get(pid, 0) + _safe_float(ic["quantidade"])

    # Comprado via compra direta
    if not cd_cot.empty:
        cd_h = cd_cot[cd_cot["unidade"].astype(str) == str(unidade)]
        for _, cd in cd_h.iterrows():
            pid = _safe_int(cd["produto_id"])
            comp[pid] = comp.get(pid, 0) + _safe_float(cd["quantidade"])

    all_pids = sorted(set(sol.keys()) | set(comp.keys()))
    hotel_data[unidade] = {"label": label, "sol": sol, "comp": comp, "pids": all_pids}

    for pid in all_pids:
        s = sol.get(pid, 0)
        c = comp.get(pid, 0)
        prod_name = str(prod_map.get(pid, {}).get("descricao", f"Produto {pid}"))
        all_prod_hoteis.append({"produto": prod_name, "hotel": label, "pid": pid, "unidade": unidade})
        if abs(s - c) > 0.001:
            all_discrepancias.append({
                "produto": prod_name,
                "hotel":   label,
                "solicitado": s,
                "comprado":   c,
                "pid":     pid,
                "unidade": unidade,
            })

# ── Interpretar nota por padrões fixos ───────────────────────────────────────
# Padrões suportados (uma entrada por linha):
#   "[produto] de [origem] para [destino]"  → transferência entre hotéis
#   "Não comprei [produto] do [hotel]"      → produto não comprado
def _interpretar_nota(nota: str, todos_prods: list) -> dict:
    if not nota.strip():
        return {}

    def _match(texto, referencia):
        return texto.lower() in referencia.lower() or referencia.lower() in texto.lower()

    result = {}
    for sent in re.split(r"[;\n]+", nota):
        sent = sent.strip()
        if not sent:
            continue

        # Padrão: [produto] de [origem] para [destino]
        m = re.search(r"(.+?)\s+de\s+(.+?)\s+para\s+(.+)", sent, re.IGNORECASE)
        if m:
            prod_txt = m.group(1).strip().rstrip(".,")
            orig_txt = m.group(2).strip().rstrip(".,")
            dest_txt = m.group(3).strip().rstrip(".,")
            for p in todos_prods:
                if _match(prod_txt, p["produto"]):
                    if _match(orig_txt, p["hotel"]):
                        result[f"{p['produto']} ({p['hotel']})"] = f"Transferido para {dest_txt}"
                    elif _match(dest_txt, p["hotel"]):
                        result[f"{p['produto']} ({p['hotel']})"] = f"Recebido do {orig_txt}"
            continue

        # Padrão: "Não comprei [produto] do [hotel]"
        m = re.search(r"n[ãa]o\s+comprei\s+(.+?)\s+do\s+(.+)", sent, re.IGNORECASE)
        if m:
            prod_txt  = m.group(1).strip().rstrip(".,")
            hotel_txt = m.group(2).strip().rstrip(".,")
            for p in todos_prods:
                if _match(prod_txt, p["produto"]) and _match(hotel_txt, p["hotel"]):
                    result[f"{p['produto']} ({p['hotel']})"] = "Não comprado"

    return result


anotacoes = {}
if nota:
    anotacoes = _interpretar_nota(nota, all_prod_hoteis)

# ── Exibir nota ───────────────────────────────────────────────────────────────
if nota:
    st.info(f"📝 **Nota do responsável:** {nota}")
elif usuario["perfil"] in ("admin", "comprador"):
    st.caption("Nenhuma nota registrada para esta cotação. Adicione em Análise de Preços → Notas da compra.")

st.markdown("---")

# ── Tabela por hotel ──────────────────────────────────────────────────────────
tem_compra = bool(comp_ids) or (not cd_cot.empty)
if not tem_compra:
    st.warning("Ainda não há registros de compra para esta cotação.")

for unidade in unidades_cot:
    hd = hotel_data[unidade]
    label = hd["label"]
    sol   = hd["sol"]
    comp  = hd["comp"]
    pids  = hd["pids"]

    if not pids:
        continue

    st.markdown(f"### 🏨 {label}")

    rows = []
    n_disc = 0
    for pid in pids:
        s = sol.get(pid, 0)
        c = comp.get(pid, 0)
        prod_name = str(prod_map.get(pid, {}).get("descricao", f"Produto {pid}"))
        diff = c - s
        chave = f"{prod_name} ({label})"
        obs = str(anotacoes.get(chave, "") or "")
        if abs(diff) < 0.001:
            status = "✅ Conforme"
        else:
            n_disc += 1
            status = "⚠️ Diferença"

        rows.append({
            "Produto":     prod_name,
            "Solicitado":  f"{s:g}" if s > 0 else "—",
            "Comprado":    f"{c:g}" if c > 0 else "—",
            "Diferença":   (f"+{diff:g}" if diff > 0 else f"{diff:g}") if abs(diff) > 0.001 else "—",
            "Status":      status,
            "Observação":  obs,
        })

    df_show = pd.DataFrame(rows)

    # Highlight rows with discrepancy
    def _color_row(row):
        if row["Status"] == "⚠️ Diferença":
            return ["background-color: #fef9c3"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df_show.style.apply(_color_row, axis=1),
        hide_index=True,
        use_container_width=True,
    )

    if n_disc == 0:
        st.success("✅ Tudo conforme para este hotel")
    else:
        st.caption(f"⚠️ {n_disc} item(ns) com diferença entre solicitado e comprado")

    st.markdown("---")
