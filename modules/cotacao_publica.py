import secrets
import streamlit as st
import pandas as pd
import datetime
from zoneinfo import ZoneInfo
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
    nome_forn = str(forn_row.iloc[0]["razao_social"]) if not forn_row.empty else "Fornecedor"

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
        "Preço e marca são obrigatórios apenas para itens marcados como **Atende**."
    )

    if "pub_form_v" not in st.session_state:
        st.session_state["pub_form_v"] = 0

    # ── Pré-montar lista de itens ─────────────────────────────────────────────
    pid_list = []
    for _, row in consolidado.iterrows():
        pid  = int(row["produto_id"])
        prod = pid_to_prod.get(pid)
        if prod is None:
            continue
        pid_list.append((pid, prod, float(row["qtd_total"])))

    # ── Seletores de situação fora do form (atualizam UI ao mudar) ────────────
    for pid, prod, qtd_total in pid_list:
        nome_prod = str(prod.get("descricao", f"Produto {pid}"))
        apres     = str(prod.get("apresentacao", ""))
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
        st.markdown("---")

    # ── Formulário: apenas itens com status = Atende ──────────────────────────
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
        st.markdown(f"### Preencha os preços — {len(itens_atende)} item(ns) marcado(s) como Atende")

        with st.form(f"cot_publica_{st.session_state['pub_form_v']}"):
            campos = {}
            for pid, prod, qtd_total in itens_atende:
                nome_prod  = str(prod.get("descricao", f"Produto {pid}"))
                ub         = str(prod.get("unidade_base", ""))
                qtd_padrao = float(prod.get("qtd_base_por_apresentacao", 1) or 1)

                st.markdown(f"**{nome_prod}** · Qtd: {qtd_total:.0f}")

                col1, col2, col3 = st.columns([2, 2, 2])
                with col1:
                    preco = st.number_input(
                        "Preço por embalagem (R$) *",
                        value=0.0, min_value=0.0, step=0.01, format="%.2f",
                        key=f"pub_preco_{pid}",
                    )
                with col2:
                    tipo_emb = st.selectbox("Tipo de embalagem", _tipos_embalagem(), key=f"pub_emb_{pid}")
                with col3:
                    qtd_emb = st.number_input(
                        f"Qtd de {ub} por embalagem",
                        value=qtd_padrao, min_value=0.001, step=0.5,
                        key=f"pub_qtdemb_{pid}",
                        help=f"Ex: caixa com 12 {ub} → informe 12",
                    )
                col_marca, col_obs = st.columns([2, 3])
                with col_marca:
                    marca = st.text_input(
                        "Marca *", key=f"pub_marca_{pid}",
                        placeholder="Ex: Sadia, Nestlé…",
                    )
                with col_obs:
                    obs = st.text_input(
                        "Observação", key=f"pub_obs_{pid}",
                        placeholder="Prazo de entrega, disponibilidade…",
                    )
                campos[pid] = {
                    "preco": preco, "tipo_embalagem": tipo_emb,
                    "qtd_por_embalagem": qtd_emb, "observacao": obs,
                    "marca": marca,
                }
                st.markdown("---")

            enviar = st.form_submit_button("📤 Enviar Cotação", use_container_width=True, type="primary")

        if enviar:
            itens_sem_preco = [pid for pid, c in campos.items() if c["preco"] <= 0]
            itens_sem_marca = [pid for pid, c in campos.items() if not str(c.get("marca", "")).strip()]
            if itens_sem_preco:
                nomes = [str(pid_to_prod.get(p, {}).get("descricao", f"#{p}")) for p in itens_sem_preco]
                st.error(f"⚠️ Informe o preço de todos os itens que você Atende: {', '.join(nomes)}")
            elif itens_sem_marca:
                nomes = [str(pid_to_prod.get(p, {}).get("descricao", f"#{p}")) for p in itens_sem_marca]
                st.error(f"⚠️ Informe a marca de todos os itens que você Atende: {', '.join(nomes)}")
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
                            c["observacao"], c.get("marca", ""), now_iso,
                        ])
                        prox_id += 1
                    from modules.google_sheets import get_sheet as _gs
                    _gs("respostas").append_rows(linhas)
                    st.session_state["pub_form_v"] += 1
                    st.cache_data.clear()
                    st.success(f"✅ Cotação enviada! {len(linhas)} item(ns) respondido(s). Obrigado!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
