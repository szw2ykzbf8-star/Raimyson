import os
import json
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

for unidade in unidades_cot:
    label = _unid_label(unidade)

    # Solicitado
    sol = {}
    peds_h = pedidos_cot[pedidos_cot["unidade"].astype(str) == str(unidade)]
    for _, ped in peds_h.iterrows():
        if df_itens_pedido.empty:
            continue
        itens = df_itens_pedido[df_itens_pedido["pedido_id"].apply(_safe_int) == _safe_int(ped["id"])]
        for _, item in itens.iterrows():
            pid = _safe_int(item["produto_id"])
            sol[pid] = sol.get(pid, 0) + _safe_float(item["quantidade"])

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
        if abs(s - c) > 0.001:
            prod_name = str(prod_map.get(pid, {}).get("descricao", f"Produto {pid}"))
            all_discrepancias.append({
                "produto": prod_name,
                "hotel":   label,
                "solicitado": s,
                "comprado":   c,
                "pid":     pid,
                "unidade": unidade,
            })

# ── Interpretar nota com Claude API ──────────────────────────────────────────
def _interpretar_nota(nota: str, discrepancias: list) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not nota.strip() or not discrepancias or not api_key:
        return {}
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        disc_text = "\n".join(
            f"- {d['produto']} ({d['hotel']}): solicitado {d['solicitado']:g}, comprado {d['comprado']:g}"
            for d in discrepancias
        )
        prompt = (
            "Você é um assistente que analisa notas de compras de hotelaria.\n\n"
            f"Nota do responsável pela compra:\n\"{nota}\"\n\n"
            "Discrepâncias encontradas entre o pedido e o que foi comprado:\n"
            f"{disc_text}\n\n"
            "Para cada discrepância, extraia a explicação relevante da nota (se houver). "
            "Responda APENAS com um objeto JSON onde a chave é exatamente \"produto (hotel)\" "
            "conforme listado e o valor é a explicação extraída, ou null se não mencionado.\n"
            "Exemplo: {\"Margarina (Hotel Monte Castelo)\": \"incluída no pedido do São Jorge por pedido mínimo\"}"
        )
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(msg.content[0].text)
    except Exception:
        return {}


anotacoes = {}
if nota and all_discrepancias:
    with st.spinner("Analisando notas da compra..."):
        anotacoes = _interpretar_nota(nota, all_discrepancias)

# ── Exibir nota ───────────────────────────────────────────────────────────────
if nota:
    st.info(f"📝 **Nota do responsável:** {nota}")
elif usuario["perfil"] in ("admin", "comprador"):
    st.caption("Nenhuma nota registrada para esta cotação. Adicione em Análise de Preços → Notas da compra.")

if not os.environ.get("ANTHROPIC_API_KEY") and all_discrepancias:
    st.warning("⚠️ Configure a variável `ANTHROPIC_API_KEY` no Railway para ativar as anotações automáticas por produto.")

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
        if abs(diff) < 0.001:
            status = "✅ Conforme"
            obs = ""
        else:
            n_disc += 1
            status = "⚠️ Diferença"
            chave = f"{prod_name} ({label})"
            obs = str(anotacoes.get(chave, "") or "")

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
