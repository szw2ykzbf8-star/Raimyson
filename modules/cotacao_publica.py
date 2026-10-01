import base64
import json as _json
import os
import secrets
import time
import unicodedata
import streamlit as st
import pandas as pd
import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import text as _sql_text
from modules.google_sheets import ler_df, append_linha
from config import TIPOS_EMBALAGEM as _TIPOS_FALLBACK

_TZ_BR = ZoneInfo("America/Sao_Paulo")


def _agora_br() -> datetime.datetime:
    return datetime.datetime.now(_TZ_BR)


def _prazo_br(iso_str: str) -> datetime.datetime:
    """Converte string ISO para datetime com fuso horário Brasil."""
    try:
        dt = datetime.datetime.fromisoformat(str(iso_str))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_TZ_BR)
        return dt.astimezone(_TZ_BR)
    except Exception:
        return datetime.datetime.max.replace(tzinfo=_TZ_BR)


def _tipos_embalagem():
    try:
        df = ler_df("unidades_medida")
        if not df.empty:
            ativos = df[df["ativo"].astype(str).str.lower().isin(["true", "1", "sim"])]
            if not ativos.empty:
                return [
                    str(r.get("nome", "")).strip()
                    for _, r in ativos.iterrows()
                    if str(r.get("nome", "")).strip()
                ]
    except Exception:
        pass
    return list(_TIPOS_FALLBACK)


def gerar_token() -> str:
    return secrets.token_urlsafe(16)


def _slugify_forn(s: str, max_len: int = 10) -> str:
    """Normalize, remove accents, keep alphanumeric, truncate."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = "".join(c if c.isalnum() else "_" for c in s)
    return s[:max_len].strip("_")


def _get_fernet():
    key = os.environ.get("COTACAO_BACKUP_KEY", "")
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        return None


def _encode_backup(data: dict) -> bytes:
    raw = _json.dumps(data, ensure_ascii=False).encode()
    f = _get_fernet()
    if f:
        return b"COTBKP1:" + base64.b64encode(f.encrypt(raw))
    return b"COTBKP0:" + base64.b64encode(raw)


def _decode_backup(raw: bytes) -> dict:
    if raw.startswith(b"COTBKP1:"):
        f = _get_fernet()
        if f is None:
            raise ValueError("Chave de backup não configurada no servidor.")
        payload = base64.b64decode(raw[len(b"COTBKP1:"):])
        return _json.loads(f.decrypt(payload))
    if raw.startswith(b"COTBKP0:"):
        payload = base64.b64decode(raw[len(b"COTBKP0:"):])
        return _json.loads(payload)
    raise ValueError("Formato de backup inválido.")


def _salvar_rascunho(token: str, dados: dict):
    from modules.database import get_engine
    engine = get_engine()
    agora = datetime.datetime.now(_TZ_BR).isoformat()
    dados_str = _json.dumps(dados, ensure_ascii=False)
    with engine.begin() as conn:
        existing = conn.execute(
            _sql_text('SELECT token FROM "rascunhos" WHERE token = :t'),
            {"t": token},
        ).fetchone()
        if existing:
            conn.execute(
                _sql_text('UPDATE "rascunhos" SET dados_json = :d, salvo_em = :s WHERE token = :t'),
                {"d": dados_str, "s": agora, "t": token},
            )
        else:
            conn.execute(
                _sql_text('INSERT INTO "rascunhos" (token, dados_json, salvo_em) VALUES (:t, :d, :s)'),
                {"t": token, "d": dados_str, "s": agora},
            )


def _carregar_rascunho(token: str):
    """Returns (dados_dict, salvo_em_str) or (None, None)."""
    from modules.database import get_engine
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            _sql_text('SELECT dados_json, salvo_em FROM "rascunhos" WHERE token = :t'),
            {"t": token},
        ).fetchone()
    if row is None:
        return None, None
    try:
        return _json.loads(row[0]), str(row[1])
    except Exception:
        return None, None


def _deletar_rascunho(token: str):
    from modules.database import get_engine
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            _sql_text('DELETE FROM "rascunhos" WHERE token = :t'),
            {"t": token},
        )


def mostrar_pagina_publica(token: str):
    """Formulário público de cotação — chamado antes do gate de autenticação."""

    st.markdown("""
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        </style>
    """, unsafe_allow_html=True)

    st.title("💰 Cotação de Preços — H Hotéis")

    # ── Validar token ─────────────────────────────────────────────────────────
    df_tokens = ler_df("cotacao_tokens")
    if df_tokens.empty:
        st.error("Link inválido.")
        st.stop()

    tok_rows = df_tokens[df_tokens["token"].astype(str) == token]
    if tok_rows.empty:
        st.error("Link inválido. Verifique se o endereço está correto.")
        st.stop()

    tok         = tok_rows.iloc[0]
    cotacao_id  = int(float(tok["cotacao_id"]))
    fornec_id   = int(float(tok["fornecedor_id"]))

    # ── Carregar cotação ──────────────────────────────────────────────────────
    df_cot  = ler_df("cotacoes")
    cot_row = df_cot[df_cot["id"].apply(lambda x: int(float(x))) == cotacao_id]
    if cot_row.empty:
        st.error("Cotação não encontrada.")
        st.stop()
    cot = cot_row.iloc[0]

    # ── Carregar nome do fornecedor ───────────────────────────────────────────
    df_forn  = ler_df("fornecedores")
    forn_row = df_forn[df_forn["id"].apply(lambda x: int(float(x))) == fornec_id]
    nome_forn = str(forn_row.iloc[0].get("nome_fantasia") or forn_row.iloc[0]["razao_social"]) if not forn_row.empty else "Fornecedor"

    # ── Verificar prazo ───────────────────────────────────────────────────────
    prazo_dt  = _prazo_br(str(cot["prazo_limite"]))
    encerrada = str(cot.get("status", "aberta")) != "aberta" or _agora_br() > prazo_dt

    st.markdown(f"### Olá, **{nome_forn}**!")
    col_p, col_c = st.columns(2)
    nome_cot = str(cot.get("nome", "") or "").strip()
    label_cot = nome_cot if nome_cot else f"nº {cotacao_id}"
    col_p.info(f"⏰ Prazo: **{prazo_dt.strftime('%d/%m/%Y às %H:%M')}**")
    col_c.info(f"Cotação: **{label_cot}**")

    if encerrada:
        st.error("⛔ Esta cotação está encerrada e não aceita mais respostas.")
        st.stop()

    # ── Carregar itens da cotação ─────────────────────────────────────────────
    df_pedidos  = ler_df("pedidos")
    df_itens    = ler_df("itens_pedido")
    df_produtos = ler_df("produtos")

    def _safe_int(v):
        try:
            return int(float(v)) if str(v).strip() not in ("", "nan") else 0
        except Exception:
            return 0

    if not df_pedidos.empty and "cotacao_id" in df_pedidos.columns:
        peds = df_pedidos[df_pedidos["cotacao_id"].apply(_safe_int) == cotacao_id]
    else:
        peds = pd.DataFrame()

    if peds.empty:
        st.warning("Nenhum item encontrado para esta cotação. Entre em contato com o comprador.")
        st.stop()

    ped_ids = peds["id"].apply(lambda x: int(float(x))).tolist()
    if not df_itens.empty:
        itens_cot = df_itens[df_itens["pedido_id"].apply(lambda x: int(float(x))).isin(ped_ids)].copy()
    else:
        itens_cot = pd.DataFrame()

    if itens_cot.empty:
        st.warning("Nenhum item encontrado.")
        st.stop()

    # Consolida quantidades por produto
    itens_cot["produto_id"] = itens_cot["produto_id"].apply(_safe_int)
    itens_cot["quantidade"]  = itens_cot["quantidade"].apply(lambda v: float(v))
    consolidado = (
        itens_cot.groupby("produto_id", as_index=False)["quantidade"]
        .sum()
        .rename(columns={"quantidade": "qtd_total"})
    )

    pid_to_prod = {int(float(r["id"])): r for _, r in df_produtos.iterrows()}

    # ── Verificar resposta anterior ───────────────────────────────────────────
    df_resp = ler_df("respostas")
    ja_respondeu = False
    if not df_resp.empty:
        resp_ex = df_resp[
            (df_resp["cotacao_id"].apply(_safe_int) == cotacao_id) &
            (df_resp["fornecedor_id"].apply(_safe_int) == fornec_id)
        ]
        ja_respondeu = not resp_ex.empty

    if ja_respondeu:
        st.success("✅ Sua resposta já foi registrada. Obrigado!")
        st.info("Para alterar seus preços, entre em contato com o comprador responsável.")
        st.stop()

    st.markdown("---")
    st.markdown("### Itens para cotação")
    st.caption(
        "Selecione a **situação** de cada item. "
        "Campos marcados com **\\*** são obrigatórios para itens **Atende** — "
        "preço 0,00 ou marca em branco bloqueiam o envio."
    )

    # ── Pré-montar lista de itens ─────────────────────────────────────────────
    pid_list = []
    for _, row in consolidado.iterrows():
        pid  = int(row["produto_id"])
        prod = pid_to_prod.get(pid)
        if prod is None:
            continue
        if str(prod.get("compra_direta", "False")).strip().lower() in ("true", "1"):
            continue
        pid_list.append((pid, prod, float(row["qtd_total"])))

    # ── Restaurar rascunho (uma vez por sessão) ────────────────────────────────
    _rasc_flag = f"pub_rascunho_ok_{token}"
    if not st.session_state.get(_rasc_flag):
        st.session_state[_rasc_flag] = True
        _rasc_dados, _rasc_ts = _carregar_rascunho(token)
        if _rasc_dados:
            for _pid_str, _vals in _rasc_dados.get("itens", {}).items():
                _pid_k = int(_pid_str)
                for _sk, _vk in [
                    (f"pub_status_{_pid_k}",    _vals.get("status", "Atende")),
                    (f"pub_preco_{_pid_k}",      float(_vals.get("preco", 0.0))),
                    (f"pub_emb_{_pid_k}",        _vals.get("tipo_embalagem", "")),
                    (f"pub_qtdemb_{_pid_k}",     float(_vals.get("qtd_por_embalagem", 1.0))),
                    (f"pub_marca_{_pid_k}",      _vals.get("marca", "")),
                    (f"pub_obs_{_pid_k}",        _vals.get("observacao", "")),
                ]:
                    if _sk not in st.session_state:
                        st.session_state[_sk] = _vk
            try:
                _ts_dt = datetime.datetime.fromisoformat(_rasc_ts).astimezone(_TZ_BR)
                st.session_state["pub_rascunho_ts"] = _ts_dt.strftime("%d/%m às %H:%M")
            except Exception:
                st.session_state["pub_rascunho_ts"] = ""

    if st.session_state.get("pub_rascunho_ts"):
        st.info(f"📂 Rascunho restaurado ({st.session_state['pub_rascunho_ts']}). Revise e envie quando estiver pronto.")

    # ── Um bloco por produto: situação + campos de preço juntos ──────────────
    for pid, prod, qtd_total in pid_list:
        nome_prod  = str(prod.get("descricao", f"Produto {pid}"))
        apres      = str(prod.get("apresentacao", ""))
        ub         = str(prod.get("unidade_base", ""))
        qtd_padrao = float(prod.get("qtd_base_por_apresentacao", 1) or 1)

        col_n, col_s = st.columns([3, 4])
        with col_n:
            st.markdown(f"**{nome_prod}**")
            st.caption(f"{apres} · Qtd solicitada: **{qtd_total:.0f}**")
        with col_s:
            st.radio(
                "Situação",
                ["Atende", "Não possui", "Não trabalha"],
                key=f"pub_status_{pid}",
                horizontal=True,
                label_visibility="collapsed",
            )

        if st.session_state.get(f"pub_status_{pid}", "Atende") == "Atende":
            if st.session_state.get("pub_tentou_enviar", False):
                _preco_v = float(st.session_state.get(f"pub_preco_{pid}", 0.0))
                _marca_v = str(st.session_state.get(f"pub_marca_{pid}", "")).strip()
                _falt = []
                if _preco_v <= 0: _falt.append("preço")
                if not _marca_v:  _falt.append("marca")
                if _falt:
                    st.markdown(
                        f'<div style="background:#fee2e2;border-left:4px solid #dc2626;'
                        f'padding:5px 12px;border-radius:4px;font-size:12px;color:#991b1b;margin:2px 0 6px">'
                        f'⚠️ Faltando: <strong>{" e ".join(_falt)}</strong></div>',
                        unsafe_allow_html=True,
                    )
            col1, col2, col3 = st.columns([2, 2, 2])
            with col1:
                st.number_input(
                    "Preço por embalagem (R$) *",
                    value=st.session_state.get(f"pub_preco_{pid}", 0.0),
                    min_value=0.0, step=0.01, format="%.2f",
                    key=f"pub_preco_{pid}",
                    help="Obrigatório. Valor 0,00 não será aceito.",
                )
            with col2:
                tipos = _tipos_embalagem()
                st.selectbox("Tipo de embalagem", tipos, key=f"pub_emb_{pid}")
            with col3:
                st.number_input(
                    f"Qtd de {ub} por embalagem",
                    value=st.session_state.get(f"pub_qtdemb_{pid}", qtd_padrao),
                    min_value=0.001, step=0.5,
                    key=f"pub_qtdemb_{pid}",
                    help=f"Ex: caixa com 12 {ub} → informe 12",
                )
            col_marca, col_obs = st.columns([2, 3])
            with col_marca:
                st.text_input(
                    "Marca *", key=f"pub_marca_{pid}",
                    placeholder="Ex: Sadia, Nestlé…",
                    help="Obrigatório. Informe a marca do produto que será entregue.",
                )
            with col_obs:
                st.text_input(
                    "Observação", key=f"pub_obs_{pid}",
                    placeholder="Prazo de entrega, disponibilidade…",
                )

        st.markdown("---")

    # ── Botão de envio ────────────────────────────────────────────────────────
    itens_atende = [
        (pid, prod, qtd_total)
        for pid, prod, qtd_total in pid_list
        if st.session_state.get(f"pub_status_{pid}", "Atende") == "Atende"
    ]

    if not itens_atende:
        st.warning(
            "Todos os itens foram marcados como *Não possui* ou *Não trabalha*. "
            "Caso isso esteja correto, entre em contato com o comprador para registrar sua indisponibilidade."
        )
    else:
        # ── Autosave a cada 30 s ──────────────────────────────────────────────
        _last_save_key = f"pub_last_save_{token}"
        if time.time() - st.session_state.get(_last_save_key, 0) >= 30:
            _rasc_itens = {
                str(_pid): {
                    "status":            st.session_state.get(f"pub_status_{_pid}", "Atende"),
                    "preco":             float(st.session_state.get(f"pub_preco_{_pid}", 0.0)),
                    "tipo_embalagem":    str(st.session_state.get(f"pub_emb_{_pid}", "")),
                    "qtd_por_embalagem": float(st.session_state.get(f"pub_qtdemb_{_pid}", 1.0)),
                    "marca":             str(st.session_state.get(f"pub_marca_{_pid}", "")),
                    "observacao":        str(st.session_state.get(f"pub_obs_{_pid}", "")),
                }
                for _pid, _, _ in pid_list
            }
            try:
                _salvar_rascunho(token, {"itens": _rasc_itens})
                st.session_state[_last_save_key] = time.time()
            except Exception:
                pass

        # ── Backup para download ──────────────────────────────────────────────
        _bkp_itens = {
            str(_pid): {
                "status":            st.session_state.get(f"pub_status_{_pid}", "Atende"),
                "preco":             float(st.session_state.get(f"pub_preco_{_pid}", 0.0)),
                "tipo_embalagem":    str(st.session_state.get(f"pub_emb_{_pid}", "")),
                "qtd_por_embalagem": float(st.session_state.get(f"pub_qtdemb_{_pid}", 1.0)),
                "marca":             str(st.session_state.get(f"pub_marca_{_pid}", "")),
                "observacao":        str(st.session_state.get(f"pub_obs_{_pid}", "")),
            }
            for _pid, _, _ in pid_list
        }
        _bkp_payload = _encode_backup({
            "cotacao_id": cotacao_id,
            "fornecedor_id": fornec_id,
            "token": token,
            "itens": _bkp_itens,
        })
        _slug_cot  = _slugify_forn(label_cot)
        _slug_forn = _slugify_forn(nome_forn)
        _data_hoje = datetime.datetime.now(_TZ_BR).strftime("%Y%m%d")
        _fname     = f"cotacao_{_slug_cot}_{_slug_forn}_{_data_hoje}.cotbkp"

        _col_bkp, _col_env = st.columns([1, 2])
        with _col_bkp:
            st.download_button(
                "💾 Salvar rascunho",
                data=_bkp_payload,
                file_name=_fname,
                mime="application/octet-stream",
                use_container_width=True,
                help="Salva um arquivo de rascunho. Se perder a conexão, o comprador pode importar este arquivo.",
            )
        _enviar = _col_env.button("📤 Enviar Cotação", use_container_width=True, type="primary")

        if _enviar:
            campos = {
                pid: {
                    "preco":            float(st.session_state.get(f"pub_preco_{pid}", 0)),
                    "tipo_embalagem":   str(st.session_state.get(f"pub_emb_{pid}", "")),
                    "qtd_por_embalagem": float(st.session_state.get(f"pub_qtdemb_{pid}", 1)),
                    "observacao":       str(st.session_state.get(f"pub_obs_{pid}", "")),
                    "marca":            str(st.session_state.get(f"pub_marca_{pid}", "")),
                }
                for pid, _, _ in itens_atende
            }
            itens_sem_preco = [pid for pid, c in campos.items() if c["preco"] <= 0]
            itens_sem_marca = [pid for pid, c in campos.items() if not c["marca"].strip()]
            erros = []
            if itens_sem_preco:
                nomes = [str(pid_to_prod.get(p, {}).get("descricao", f"#{p}")) for p in itens_sem_preco]
                erros.append(f"**Preço não informado (0,00):** {', '.join(nomes)}")
            if itens_sem_marca:
                nomes = [str(pid_to_prod.get(p, {}).get("descricao", f"#{p}")) for p in itens_sem_marca]
                erros.append(f"**Marca não informada:** {', '.join(nomes)}")
            if erros:
                st.session_state["pub_tentou_enviar"] = True
                st.error("⚠️ Verifique os campos obrigatórios marcados acima.")
            else:
                try:
                    df_resp2 = ler_df("respostas")
                    prox_id  = int(df_resp2["id"].max()) + 1 if not df_resp2.empty else 1
                    now_iso  = datetime.datetime.now().isoformat()
                    linhas   = []
                    for pid, c in campos.items():
                        linhas.append([
                            prox_id, cotacao_id, fornec_id, pid,
                            c["preco"], c["tipo_embalagem"], c["qtd_por_embalagem"],
                            c["observacao"], c["marca"], now_iso,
                        ])
                        prox_id += 1
                    from modules.google_sheets import get_sheet as _gs
                    _gs("respostas").append_rows(linhas)
                    _deletar_rascunho(token)
                    st.cache_data.clear()
                    st.session_state.pop("pub_tentou_enviar", None)
                    st.success(f"✅ Cotação enviada! {len(linhas)} item(ns) respondido(s). Obrigado!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
