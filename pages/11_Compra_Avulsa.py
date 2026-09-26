import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import datetime

from modules.auth import requer_permissao
from modules.google_sheets import ler_df, escrever_df, append_linha

usuario = requer_permissao("compra_avulsa")

st.title("🧾 Compra Avulsa")
st.caption("Importe NF-e de compras realizadas fora do sistema — sem cotação ou pedido prévio.")

# ── Helpers ───────────────────────────────────────────────────────────────────

_NS = "http://www.portalfiscal.inf.br/nfe"


def _t(el, tag):
    return el.findtext(f"{{{_NS}}}{tag}") or ""


def limpar_cnpj(cnpj):
    return "".join(c for c in (cnpj or "") if c.isdigit())


def formatar_cnpj(digits):
    d = limpar_cnpj(digits)
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"
    return digits


def formatar_telefone(raw):
    d = "".join(c for c in (raw or "") if c.isdigit())
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return raw or ""


def consultar_cnpj_api(cnpj_digits):
    try:
        import requests
        resp = requests.get(
            f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_digits}",
            timeout=15,
            headers={"User-Agent": "H-Hoteis-Compras/1.0"},
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def parse_nfe(xml_bytes):
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
    dest      = inf.find(f"{{{_NS}}}dest")
    tot       = inf.find(f".//{{{_NS}}}ICMSTot")
    numero    = _t(ide,  "nNF")   if ide  is not None else ""
    serie     = _t(ide,  "serie") if ide  is not None else ""
    demi      = _t(ide,  "dhEmi") if ide  is not None else ""
    cnpj_emit = (_t(emit, "CNPJ") or _t(emit, "CPF")) if emit is not None else ""
    nome_emit = _t(emit, "xNome") if emit is not None else ""
    cnpj_dest = (_t(dest, "CNPJ") or _t(dest, "CPF")) if dest is not None else ""
    nome_dest = _t(dest, "xNome") if dest is not None else ""
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
        "chave":      chave,
        "numero":     numero,
        "serie":      serie,
        "data":       demi[:10] if demi else "",
        "cnpj_emit":  cnpj_emit,
        "nome_emit":  nome_emit,
        "cnpj_dest":  cnpj_dest,
        "nome_dest":  nome_dest,
        "valor_total": vNF,
        "itens":      itens,
    }


# ── Load data ─────────────────────────────────────────────────────────────────

df_fornec     = ler_df("fornecedores")
df_unidades   = ler_df("unidades")
df_produtos   = ler_df("produtos")
df_mapeamento = ler_df("nfe_mapeamento")
df_compras    = ler_df("compras")

# ── Product lookup ────────────────────────────────────────────────────────────

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

pid_to_prod = {int(r["id"]): r for _, r in df_produtos.iterrows()}

map_lookup = {}
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


# ── Section 1: Load XML ───────────────────────────────────────────────────────

st.subheader("1. Carregar XML da NF-e")
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
                st.session_state["_avulsa_xml_cache"] = xml_bytes
            except Exception as e:
                st.error(f"Erro ao buscar URL: {e}")
        elif "_avulsa_xml_cache" in st.session_state:
            xml_bytes = st.session_state["_avulsa_xml_cache"]

if xml_bytes is None:
    st.stop()

# ── Parse ─────────────────────────────────────────────────────────────────────

try:
    nfe = parse_nfe(xml_bytes)
except Exception as e:
    st.error(f"Erro ao interpretar XML: {e}")
    st.stop()

st.session_state.pop("_avulsa_xml_cache", None)

# Duplicate check
if not df_compras.empty and "nfe_chave" in df_compras.columns and nfe["chave"]:
    dup = df_compras[df_compras["nfe_chave"].astype(str).str.strip() == nfe["chave"].strip()]
    if not dup.empty:
        st.warning(
            f"⚠️ Esta NF-e já foi importada como Compra #{int(dup.iloc[0]['id'])}. "
            "Você pode continuar, mas uma duplicata será criada."
        )

col1, col2, col3, col4 = st.columns(4)
col1.metric("NF-e Nº", f"{nfe['numero']}/{nfe['serie']}")
col2.metric("Data Emissão", nfe["data"])
col3.metric("Emitente", nfe["nome_emit"] or nfe["cnpj_emit"])
col4.metric("Valor Total", f"R$ {nfe['valor_total']:,.2f}")

if not nfe["itens"]:
    st.warning("O XML não contém itens.")
    st.stop()

# ── Section 2: Unit & Supplier detection ─────────────────────────────────────

st.markdown("---")
st.subheader("2. Destinatário e Fornecedor")

# Identify unit from dest.CNPJ
cnpj_dest_digits = limpar_cnpj(nfe["cnpj_dest"])
unidade_detectada = None
if not df_unidades.empty:
    for _, row in df_unidades.iterrows():
        cnpj_u = limpar_cnpj(str(row.get("cnpj", "") or ""))
        if cnpj_u and cnpj_u == cnpj_dest_digits:
            unidade_detectada = str(row["nome"])
            break

col_u, col_f = st.columns(2)

with col_u:
    st.markdown("**Destinatário (Unidade)**")
    if unidade_detectada:
        st.success(f"✅ {unidade_detectada}")
        st.caption(f"CNPJ da nota: {formatar_cnpj(cnpj_dest_digits) or nfe['cnpj_dest']}")
    else:
        st.warning(
            f"CNPJ {nfe['cnpj_dest']} ({nfe['nome_dest']}) não corresponde a nenhuma "
            "unidade cadastrada. Selecione manualmente:"
        )
        opcoes_und = ["— Selecionar —"] + (df_unidades["nome"].tolist() if not df_unidades.empty else [])
        sel_und = st.selectbox("Unidade", opcoes_und, key="avulsa_und_manual")
        if sel_und != "— Selecionar —":
            unidade_detectada = sel_und

# Identify supplier from emit.CNPJ
cnpj_emit_digits = limpar_cnpj(nfe["cnpj_emit"])
fornecedor_id_existente = None
if not df_fornec.empty:
    for _, row in df_fornec.iterrows():
        cnpj_f = limpar_cnpj(str(row.get("cnpj", "") or ""))
        if cnpj_f and cnpj_f == cnpj_emit_digits:
            fornecedor_id_existente = int(row["id"])
            break

with col_f:
    st.markdown("**Fornecedor (Emitente)**")
    if fornecedor_id_existente is not None:
        frow = df_fornec[df_fornec["id"].apply(lambda x: int(float(x))) == fornecedor_id_existente].iloc[0]
        st.success(f"✅ {frow.get('nome_fantasia') or frow['razao_social']}")
        st.caption(f"CNPJ: {frow.get('cnpj', formatar_cnpj(cnpj_emit_digits))}")
    else:
        st.info(
            f"Fornecedor com CNPJ {formatar_cnpj(cnpj_emit_digits)} não cadastrado — "
            "será registrado automaticamente via Receita Federal ao confirmar."
        )

if unidade_detectada is None:
    st.info("Selecione a unidade destinatária acima para continuar.")
    st.stop()

# ── Section 3: Match items ────────────────────────────────────────────────────

st.markdown("---")
st.subheader("3. Vincular Itens da Nota com Produtos")
st.caption(
    "✅ = código do produto bate com o `cProd` da nota  |  "
    "🔗 = vínculo salvo anteriormente  |  "
    "❓ = selecione manualmente"
)

fid_for_lookup = fornecedor_id_existente or 0

salvar_mapas = st.checkbox(
    "Salvar novos vínculos para este fornecedor (próximas notas serão reconhecidas automaticamente)",
    value=True,
)

vinculacoes = {}
qtds_rec    = {}

for i, item in enumerate(nfe["itens"]):
    cprod_low = item["cprod"].strip().lower()

    pid_auto = cod_to_pid.get(cprod_low)
    if pid_auto is None and fid_for_lookup:
        pid_auto = map_lookup.get((fid_for_lookup, cprod_low))

    tag = "✅" if pid_auto and cprod_low in cod_to_pid else ("🔗" if pid_auto else "❓")

    with st.expander(f"{tag} Item {item['n_item']}: {item['xprod']}  —  {item['qtd']} {item['unidade']}  (cProd: {item['cprod']})"):
        col_a, col_b = st.columns([3, 1])
        with col_a:
            sel = st.selectbox(
                "Produto no sistema",
                opts_label,
                index=pid_default_idx(pid_auto),
                key=f"avulsa_vinc_{i}",
            )
            vinculacoes[i] = opts_id[opts_label.index(sel)]
        with col_b:
            qtd_rec = st.number_input(
                "Qtd comprada",
                value=item["qtd"],
                min_value=0.0,
                step=0.5,
                key=f"avulsa_qtd_{i}",
                help=f"Nota: {item['qtd']} {item['unidade']}",
            )
            qtds_rec[i] = qtd_rec
            st.caption(f"R$ {item['vunit']:.4f}/{item['unidade']}")

# ── Section 4: Confirm ────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("4. Confirmar Compra")

itens_para_salvar = [(i, vinculacoes[i], qtds_rec[i]) for i in vinculacoes if vinculacoes[i] is not None]
itens_ignorados   = sum(1 for v in vinculacoes.values() if v is None)

if not itens_para_salvar:
    st.warning("Nenhum item vinculado a um produto. Selecione ao menos um produto acima.")
    st.stop()

# Preview table
pid_to_desc = {int(r["id"]): r["descricao"] for _, r in df_produtos.iterrows()}
preview_rows = []
for i, pid, qtd in itens_para_salvar:
    item     = nfe["itens"][i]
    prod_row = pid_to_prod.get(pid, {})
    fator    = float(prod_row.get("qtd_base_por_apresentacao", 1) or 1)
    preco_norm = item["vunit"] / fator if fator else item["vunit"]
    preview_rows.append({
        "Produto":      pid_to_desc.get(pid, f"ID {pid}"),
        "cProd NF-e":   item["cprod"],
        "Qtd":          qtd,
        "Preço Unit.":  f"R$ {item['vunit']:.4f}",
        "Preço/base":   f"R$ {preco_norm:.4f}",
        "Total":        f"R$ {item['vtotal']:.2f}",
    })

st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
if itens_ignorados:
    st.caption(f"⚠️ {itens_ignorados} item(ns) ignorado(s) — não serão registrados.")

col_inf1, col_inf2 = st.columns(2)
col_inf1.info(f"**Unidade:** {unidade_detectada}")
if fornecedor_id_existente is not None:
    frow = df_fornec[df_fornec["id"].apply(lambda x: int(float(x))) == fornecedor_id_existente].iloc[0]
    col_inf2.info(f"**Fornecedor:** {frow.get('nome_fantasia') or frow['razao_social']}")
else:
    col_inf2.info(f"**Fornecedor:** {nfe['nome_emit'] or formatar_cnpj(cnpj_emit_digits)} *(será cadastrado)*")

if st.button(f"✅ Confirmar Compra Avulsa ({len(itens_para_salvar)} itens)", use_container_width=True, type="primary"):
    erros = []
    try:
        from modules.google_sheets import get_sheet as _gs

        fid = fornecedor_id_existente

        # 1. Auto-register supplier if needed
        if fid is None:
            with st.spinner("Buscando fornecedor na Receita Federal…"):
                api_data = consultar_cnpj_api(cnpj_emit_digits)

            df_f2 = ler_df("fornecedores")
            novo_fid = int(df_f2["id"].max()) + 1 if not df_f2.empty else 1

            if api_data:
                tipo = api_data.get("descricao_tipo_de_logradouro", "") or ""
                logr = api_data.get("logradouro", "") or ""
                logradouro = f"{tipo} {logr}".strip() if tipo else logr
                append_linha("fornecedores", [
                    novo_fid,
                    api_data.get("razao_social", "") or nfe["nome_emit"],
                    formatar_cnpj(cnpj_emit_digits),
                    "",
                    formatar_telefone(api_data.get("ddd_telefone_1", "") or ""),
                    True,
                    datetime.date.today().isoformat(),
                    api_data.get("nome_fantasia", "") or "",
                    api_data.get("cep", "") or "",
                    logradouro,
                    api_data.get("numero", "") or "",
                    api_data.get("complemento", "") or "",
                    api_data.get("bairro", "") or "",
                    api_data.get("municipio", "") or "",
                    api_data.get("uf", "") or "",
                ])
                st.info(f"Fornecedor '{api_data.get('razao_social', nfe['nome_emit'])}' cadastrado automaticamente.")
            else:
                append_linha("fornecedores", [
                    novo_fid,
                    nfe["nome_emit"] or formatar_cnpj(cnpj_emit_digits),
                    formatar_cnpj(cnpj_emit_digits),
                    "", "", True,
                    datetime.date.today().isoformat(),
                    "", "", "", "", "", "", "", "",
                ])
                st.warning("Consulta à Receita Federal falhou. Fornecedor cadastrado com dados básicos da nota.")

            fid = novo_fid

        # 2. Create Compras record
        df_c2 = ler_df("compras")
        nova_compra_id = int(df_c2["id"].max()) + 1 if not df_c2.empty else 1
        append_linha("compras", [
            nova_compra_id,
            "",   # cotacao_id
            fid,
            nfe["data"] or datetime.date.today().isoformat(),
            nfe["valor_total"],
            False,
            nfe["chave"],
            f"{nfe['numero']}/{nfe['serie']}",
            "recebido",
            unidade_detectada,
        ])

        # 3. Create ItensCompra + HistoricoPrecos records
        df_ic = ler_df("itens_compra")
        prox_ic = int(df_ic["id"].max()) + 1 if not df_ic.empty else 1

        df_hp = ler_df("historico_precos")
        prox_hp = int(df_hp["id"].max()) + 1 if not df_hp.empty else 1

        linhas_ic   = []
        linhas_hp   = []
        novos_mapas = []

        for i, pid, qtd in itens_para_salvar:
            item     = nfe["itens"][i]
            prod_row = pid_to_prod.get(pid, {})
            fator    = float(prod_row.get("qtd_base_por_apresentacao", 1) or 1)
            apres    = str(prod_row.get("apresentacao", item["unidade"]) or item["unidade"])
            preco_norm = item["vunit"] / fator if fator else item["vunit"]

            linhas_ic.append([prox_ic, nova_compra_id, pid, qtd, item["vunit"], preco_norm, fator])
            prox_ic += 1

            linhas_hp.append([
                prox_hp, pid, fid, "",
                item["vunit"], apres, fator, preco_norm, True,
                nfe["data"] or datetime.date.today().isoformat(),
            ])
            prox_hp += 1

            cprod_low = item["cprod"].strip().lower()
            key = (fid, cprod_low)
            if salvar_mapas and key not in map_lookup and cprod_low not in cod_to_pid:
                novos_mapas.append((fid, item["cprod"].strip(), pid))

        if linhas_ic:
            _gs("itens_compra").append_rows(linhas_ic)

        if linhas_hp:
            _gs("historico_precos").append_rows(linhas_hp)

        # 4. Save new NF-e mappings
        if salvar_mapas and novos_mapas:
            df_m2 = ler_df("nfe_mapeamento")
            prox_m = int(df_m2["id"].max()) + 1 if not df_m2.empty else 1
            linhas_mapa = []
            for fid_m, cprod_m, pid_m in novos_mapas:
                linhas_mapa.append([prox_m, fid_m, cprod_m, pid_m])
                prox_m += 1
            _gs("nfe_mapeamento").append_rows(linhas_mapa)

    except Exception as e:
        erros.append(str(e))

    if erros:
        st.error(f"Erro ao salvar: {erros[0]}")
    else:
        st.success(
            f"✅ Compra Avulsa registrada! "
            f"NF-e {nfe['numero']}/{nfe['serie']} — {unidade_detectada}. "
            "O XML não foi armazenado."
        )
        st.cache_data.clear()
        st.rerun()
