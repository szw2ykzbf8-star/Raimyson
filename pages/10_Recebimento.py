import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import datetime

from modules.auth import requer_permissao
from modules.google_sheets import ler_df, escrever_df, append_linha

usuario = requer_permissao("recebimento")

st.title("📥 Recebimento de NF-e")

# ── NF-e parser ──────────────────────────────────────────────────────────────

_NS = "http://www.portalfiscal.inf.br/nfe"


def _t(el, tag: str) -> str:
    return el.findtext(f"{{{_NS}}}{tag}") or ""


def parse_nfe(xml_bytes) -> dict:
    if isinstance(xml_bytes, (bytes, bytearray)):
        root = ET.fromstring(xml_bytes)
    else:
        root = ET.fromstring(xml_bytes.encode())

    inf = root.find(f".//{{{_NS}}}infNFe")
    if inf is None:
        raise ValueError("XML não contém infNFe — verifique se é uma NF-e válida.")

    chave     = inf.get("Id", "").replace("NFe", "")
    ide       = inf.find(f"{{{_NS}}}ide")
    emit      = inf.find(f"{{{_NS}}}emit")
    tot       = inf.find(f".//{{{_NS}}}ICMSTot")
    numero    = _t(ide,  "nNF")   if ide  is not None else ""
    serie     = _t(ide,  "serie") if ide  is not None else ""
    demi      = _t(ide,  "dhEmi") if ide  is not None else ""
    cnpj_emit = (_t(emit, "CNPJ") or _t(emit, "CPF")) if emit is not None else ""
    nome_emit = _t(emit, "xNome") if emit is not None else ""
    vNF       = float(_t(tot, "vNF") or 0) if tot is not None else 0.0

    itens = []
    for det in inf.findall(f"{{{_NS}}}det"):
        prod = det.find(f"{{{_NS}}}prod")
        if prod is None:
            continue
        itens.append({
            "n_item":  det.get("nItem", ""),
            "cprod":   _t(prod, "cProd"),
            "xprod":   _t(prod, "xProd"),
            "qtd":     float(_t(prod, "qCom") or 0),
            "unidade": _t(prod, "uCom"),
            "vunit":   float(_t(prod, "vUnCom") or 0),
            "vtotal":  float(_t(prod, "vProd") or 0),
        })

    return {
        "chave":       chave,
        "numero":      numero,
        "serie":       serie,
        "data":        demi[:10] if demi else "",
        "cnpj_emit":   cnpj_emit,
        "nome_emit":   nome_emit,
        "valor_total": vNF,
        "itens":       itens,
    }


# ── Load data ────────────────────────────────────────────────────────────────

df_compras     = ler_df("compras")
df_fornec      = ler_df("fornecedores")
df_itens_c     = ler_df("itens_compra")
df_produtos    = ler_df("produtos")
df_mapeamento  = ler_df("nfe_mapeamento")
df_unidades    = ler_df("unidades")

# ── Build product lookup ──────────────────────────────────────────────────────

opts_label = ["— Ignorar item —"]
opts_id    = [None]
for _, r in df_produtos.iterrows():
    cod   = str(r.get("codigo", "") or "").strip()
    label = f"[{cod}] {r['descricao']}" if cod else str(r["descricao"])
    opts_label.append(label)
    opts_id.append(int(r["id"]))

cod_to_pid = {}
for _, r in df_produtos.iterrows():
    cod = str(r.get("codigo", "") or "").strip().lower()
    if cod:
        cod_to_pid[cod] = int(r["id"])

map_lookup = {}  # (fornecedor_id, cprod_lower) -> produto_id
if not df_mapeamento.empty:
    for _, r in df_mapeamento.iterrows():
        key = (int(float(r["fornecedor_id"])), str(r["nfe_cprod"]).strip().lower())
        map_lookup[key] = int(float(r["produto_id"]))


def pid_default_idx(produto_id):
    if produto_id is None:
        return 0
    try:
        return opts_id.index(produto_id)
    except ValueError:
        return 0


# ── Section 1: Select purchase order ─────────────────────────────────────────

st.subheader("1. Selecionar Ordem de Compra")

if df_compras.empty:
    st.info("Nenhuma compra registrada ainda.")
    st.stop()

nome_fornec = {}
if not df_fornec.empty:
    for _, r in df_fornec.iterrows():
        nome_fornec[int(r["id"])] = str(r["razao_social"])

unid_fantasia = {}
if not df_unidades.empty:
    for _, r in df_unidades.iterrows():
        _nm = str(r.get("nome", "") or "").strip()
        _nf = str(r.get("nome_fantasia", "") or "").strip()
        if _nm:
            unid_fantasia[_nm] = _nf if _nf else _nm

compras_opts = {"— Selecione —": None}
for _, r in df_compras.iterrows():
    fid    = int(float(r.get("fornecedor_id") or 0))
    fnome  = nome_fornec.get(fid, f"Fornecedor {fid}")
    unid   = str(r.get("unidade", "") or "").strip()
    hotel  = unid_fantasia.get(unid, unid)
    data   = str(r.get("data_compra", ""))[:10]
    status = str(r.get("status_recebimento", "") or "pendente")
    chave  = str(r.get("nfe_chave", "") or "").strip()
    icone  = "✅" if chave else "🕐"
    hotel_part = f" — {hotel}" if hotel else ""
    label  = f"{icone} Compra #{int(r['id'])} — {fnome}{hotel_part} — {data} — {status}"
    compras_opts[label] = int(r["id"])

compra_sel_label = st.selectbox("Ordem de Compra", list(compras_opts.keys()))
compra_id = compras_opts[compra_sel_label]

if compra_id is None:
    st.stop()

compra_row = df_compras[df_compras["id"].apply(lambda x: int(float(x))) == compra_id].iloc[0]
compra_forn_id = int(float(compra_row.get("fornecedor_id") or 0))

itens_pedido = df_itens_c[
    df_itens_c["compra_id"].apply(lambda x: int(float(x))) == compra_id
].copy() if not df_itens_c.empty else pd.DataFrame()

pid_to_qtd_pedida = {}
if not itens_pedido.empty:
    for _, r in itens_pedido.iterrows():
        pid_to_qtd_pedida[int(float(r["produto_id"]))] = float(r.get("quantidade") or 0)

# ── Section 2: Load XML ───────────────────────────────────────────────────────

st.markdown("---")
st.subheader("2. Carregar XML da NF-e")
st.caption("O XML não é armazenado — apenas os dados necessários são salvos após a confirmação.")

fonte = st.radio("Fonte do XML", ["Upload de arquivo", "URL (link do Omie ou similar)"], horizontal=True)

xml_bytes = None

if fonte == "Upload de arquivo":
    arq = st.file_uploader("Arquivo XML da NF-e", type=["xml"])
    if arq:
        xml_bytes = arq.read()
else:
    url_xml = st.text_input(
        "URL do XML",
        placeholder="https://app.omie.com.br/resources/temp/…-procnfe.xml?…",
    )
    if url_xml.strip():
        if st.button("🔗 Buscar XML pela URL"):
            try:
                import requests as _req
                resp = _req.get(
                    url_xml.strip(),
                    timeout=20,
                    headers={"User-Agent": "H-Hoteis-Compras/1.0"},
                )
                resp.raise_for_status()
                xml_bytes = resp.content
                st.session_state["_nfe_xml_cache"] = xml_bytes
            except Exception as e:
                st.error(f"Erro ao buscar URL: {e}")
        elif "_nfe_xml_cache" in st.session_state:
            xml_bytes = st.session_state["_nfe_xml_cache"]

if xml_bytes is None:
    st.stop()

# ── Parse ─────────────────────────────────────────────────────────────────────

try:
    nfe = parse_nfe(xml_bytes)
except Exception as e:
    st.error(f"Erro ao interpretar XML: {e}")
    st.stop()

# Clear URL cache after successful parse (don't keep XML in memory)
st.session_state.pop("_nfe_xml_cache", None)

col1, col2, col3, col4 = st.columns(4)
col1.metric("NF-e Nº", f"{nfe['numero']}/{nfe['serie']}")
col2.metric("Data Emissão", nfe["data"])
col3.metric("Emitente", nfe["nome_emit"] or nfe["cnpj_emit"])
col4.metric("Valor Total", f"R$ {nfe['valor_total']:,.2f}")

if not nfe["itens"]:
    st.warning("O XML não contém itens.")
    st.stop()

# ── Section 3: Match items ────────────────────────────────────────────────────

st.markdown("---")
st.subheader("3. Vincular Itens da Nota com Produtos")
st.caption(
    "✅ = código do produto bate exatamente com o `cProd` da nota  |  "
    "🔗 = vínculo salvo anteriormente  |  "
    "❓ = selecione manualmente"
)

salvar_mapas = st.checkbox(
    "Salvar novos vínculos para este fornecedor (próximas notas serão reconhecidas automaticamente)",
    value=True,
)

vinculacoes = {}   # idx -> produto_id (ou None = ignorar)
qtds_rec    = {}   # idx -> float

for i, item in enumerate(nfe["itens"]):
    cprod_low = item["cprod"].strip().lower()

    # Auto-match priority: exact code > saved mapping
    pid_auto = cod_to_pid.get(cprod_low)
    if pid_auto is None:
        pid_auto = map_lookup.get((compra_forn_id, cprod_low))

    if pid_auto is not None:
        tag = "✅" if cprod_low in cod_to_pid else "🔗"
    else:
        tag = "❓"

    with st.expander(f"{tag} Item {item['n_item']}: {item['xprod']}  —  {item['qtd']} {item['unidade']}  (cProd: {item['cprod']})"):
        col_a, col_b = st.columns([3, 1])
        with col_a:
            sel = st.selectbox(
                "Produto no sistema",
                opts_label,
                index=pid_default_idx(pid_auto),
                key=f"vinc_{i}",
            )
            vinculacoes[i] = opts_id[opts_label.index(sel)]
        with col_b:
            qtd_ped = pid_to_qtd_pedida.get(vinculacoes[i], 0.0) if vinculacoes[i] else 0.0
            qtd_rec = st.number_input(
                "Qtd recebida",
                value=item["qtd"],
                min_value=0.0,
                step=0.5,
                key=f"qtd_rec_{i}",
                help=f"Pedido: {qtd_ped}  |  Nota: {item['qtd']}",
            )
            qtds_rec[i] = qtd_rec

# ── Section 4: Confirm ────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("4. Confirmar Recebimento")

itens_para_salvar = [(i, vinculacoes[i], qtds_rec[i]) for i in vinculacoes if vinculacoes[i] is not None]
itens_ignorados   = sum(1 for v in vinculacoes.values() if v is None)

if not itens_para_salvar:
    st.warning("Nenhum item vinculado a um produto. Selecione ao menos um produto acima.")
    st.stop()

# Build preview table
preview_rows = []
pid_to_desc = {int(r["id"]): r["descricao"] for _, r in df_produtos.iterrows()}
for i, pid, qtd_rec in itens_para_salvar:
    item = nfe["itens"][i]
    qtd_ped = pid_to_qtd_pedida.get(pid, "—")
    diff = qtd_rec - float(qtd_ped) if isinstance(qtd_ped, float) else "—"
    preview_rows.append({
        "Produto":      pid_to_desc.get(pid, f"ID {pid}"),
        "cProd NF-e":   item["cprod"],
        "Desc. NF-e":   item["xprod"],
        "Qtd Pedida":   qtd_ped,
        "Qtd Recebida": qtd_rec,
        "Diferença":    diff,
    })

st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

if itens_ignorados:
    st.caption(f"⚠️ {itens_ignorados} item(ns) ignorado(s) — não serão registrados.")

tem_divergencia = any(
    r["Diferença"] != 0 and r["Diferença"] != "—"
    for r in preview_rows
)
status_rec = "divergente" if tem_divergencia else "recebido"

if st.button(f"✅ Confirmar Recebimento ({len(itens_para_salvar)} itens)", use_container_width=True, type="primary"):
    erros = []
    try:
        # 1. Gravar ItensRecebimento
        df_ir = ler_df("itens_recebimento")
        prox_id = int(df_ir["id"].max()) + 1 if not df_ir.empty else 1
        novas_ir = []
        novos_mapas = []

        for i, pid, qtd_rec in itens_para_salvar:
            item = nfe["itens"][i]
            qtd_ped = pid_to_qtd_pedida.get(pid, 0.0)
            novas_ir.append([prox_id, compra_id, pid, float(qtd_ped), float(qtd_rec)])
            prox_id += 1

            # New mapping to save?
            cprod_low = item["cprod"].strip().lower()
            key = (compra_forn_id, cprod_low)
            if salvar_mapas and key not in map_lookup and cprod_low not in cod_to_pid:
                novos_mapas.append([pid, item["cprod"], pid])  # tmp, rewrite below

        if novas_ir:
            from modules.google_sheets import get_sheet as _gs
            _gs("itens_recebimento").append_rows(novas_ir)

        # 2. Salvar novos mapeamentos
        if salvar_mapas and novos_mapas:
            df_m2 = ler_df("nfe_mapeamento")
            prox_m = int(df_m2["id"].max()) + 1 if not df_m2.empty else 1
            linhas_mapa = []
            for i, pid, qtd_rec in itens_para_salvar:
                item = nfe["itens"][i]
                cprod_low = item["cprod"].strip().lower()
                key = (compra_forn_id, cprod_low)
                if key not in map_lookup and cprod_low not in cod_to_pid:
                    linhas_mapa.append([prox_m, compra_forn_id, item["cprod"].strip(), pid])
                    prox_m += 1
            if linhas_mapa:
                _gs("nfe_mapeamento").append_rows(linhas_mapa)

        # 3. Atualizar Compras: nfe_chave, nfe_numero, status_recebimento
        df_c2 = ler_df("compras")
        idx_c = df_c2[df_c2["id"].apply(lambda x: int(float(x))) == compra_id].index
        if len(idx_c):
            ic = idx_c[0]
            df_c2["nfe_chave"]          = df_c2["nfe_chave"].astype(object)
            df_c2["nfe_numero"]         = df_c2["nfe_numero"].astype(object)
            df_c2["status_recebimento"] = df_c2["status_recebimento"].astype(object)
            df_c2.at[ic, "nfe_chave"]          = nfe["chave"]
            df_c2.at[ic, "nfe_numero"]         = f"{nfe['numero']}/{nfe['serie']}"
            df_c2.at[ic, "status_recebimento"] = status_rec
            escrever_df("compras", df_c2)

    except Exception as e:
        erros.append(str(e))

    if erros:
        st.error(f"Erro ao salvar: {erros[0]}")
    else:
        icone_status = "⚠️" if status_rec == "divergente" else "✅"
        st.success(
            f"{icone_status} Recebimento registrado! "
            f"NF-e {nfe['numero']}/{nfe['serie']} — status: **{status_rec}**. "
            "O XML não foi armazenado."
        )
        st.cache_data.clear()
        st.rerun()
