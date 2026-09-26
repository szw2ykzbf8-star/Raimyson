import streamlit as st
import pandas as pd
import datetime
from zoneinfo import ZoneInfo
from modules.auth import requer_permissao
from modules.google_sheets import ler_df, escrever_df, append_linha, get_sheet
from modules.cotacao_publica import gerar_token, _prazo_br, _agora_br
from config import TIPOS_EMBALAGEM, BASE_URL

usuario = requer_permissao("cotacoes")

st.title("💰 Cotações")

df_pedidos     = ler_df("pedidos")
df_itens       = ler_df("itens_pedido")
df_produtos    = ler_df("produtos")
df_fornecedores = ler_df("fornecedores")
df_cotacoes    = ler_df("cotacoes")
df_respostas   = ler_df("respostas")
df_tokens      = ler_df("cotacao_tokens")

def _safe_int(v):
    try:
        return int(float(v)) if str(v).strip() not in ("", "nan") else 0
    except Exception:
        return 0


tab_nova, tab_abertas, tab_encerradas = st.tabs(["Nova Cotação", "Em Andamento", "Encerradas"])

# ── Nova Cotação ──────────────────────────────────────────────────────────────
with tab_nova:
    st.subheader("Consolidar pedidos e iniciar cotação")

    pedidos_bloqueados = (
        df_pedidos[df_pedidos["status"] == "bloqueado"]
        if not df_pedidos.empty else pd.DataFrame()
    )

    if pedidos_bloqueados.empty:
        st.info("Nenhum pedido bloqueado aguardando cotação.")
    else:
        st.write("Pedidos prontos para cotação:")
        for _, ped in pedidos_bloqueados.iterrows():
            itens = df_itens[df_itens["pedido_id"] == ped["id"]] if not df_itens.empty else pd.DataFrame()
            st.write(f"• **#{ped['id']}** — {ped['unidade']} ({len(itens)} itens)")

        st.markdown("---")
        nome_cot = st.text_input(
            "Nome da cotação (ex: Semana 40, Hotel Centro Out/25)",
            placeholder="Nome para identificar esta cotação",
        )
        prazo = st.date_input(
            "Data limite para resposta dos fornecedores",
            value=datetime.date.today() + datetime.timedelta(days=1),
            format="DD/MM/YYYY",
        )
        hora = st.time_input("Hora limite", value=datetime.time(12, 0), step=3600)
        prazo_completo = datetime.datetime.combine(prazo, hora).isoformat()

        fornecedores_ativos = (
            df_fornecedores[df_fornecedores["ativo"] == True]
            if not df_fornecedores.empty else pd.DataFrame()
        )
        if not fornecedores_ativos.empty:
            selecionados = st.multiselect(
                "Fornecedores para esta cotação",
                options=fornecedores_ativos["id"].tolist(),
                format_func=lambda x: fornecedores_ativos[
                    fornecedores_ativos["id"] == x
                ]["razao_social"].values[0],
            )
        else:
            st.warning("Nenhum fornecedor ativo cadastrado.")
            selecionados = []

        if st.button("Iniciar Cotação", type="primary"):
            if not selecionados:
                st.error("Selecione ao menos um fornecedor.")
            else:
                novo_id = int(df_cotacoes["id"].max()) + 1 if not df_cotacoes.empty else 1

                # Criar cotação
                append_linha("cotacoes", [
                    novo_id, datetime.datetime.now().isoformat(),
                    prazo_completo, "aberta", usuario["nome"], nome_cot,
                ])

                # Gerar token por fornecedor
                tok_id = (
                    int(df_tokens["id"].max()) + 1
                    if not df_tokens.empty else 1
                )
                token_rows = []
                links = {}
                for fid in selecionados:
                    tok = gerar_token()
                    token_rows.append([tok_id, novo_id, fid, tok])
                    nome_forn = fornecedores_ativos[
                        fornecedores_ativos["id"] == fid
                    ]["razao_social"].values[0]
                    links[nome_forn] = f"{BASE_URL}/?token={tok}"
                    tok_id += 1

                get_sheet("cotacao_tokens").append_rows(token_rows)

                # Atualizar pedidos: status → em_cotacao, cotacao_id
                if not df_pedidos.empty:
                    for _, ped in pedidos_bloqueados.iterrows():
                        idx = df_pedidos[df_pedidos["id"] == ped["id"]].index[0]
                        df_pedidos.at[idx, "status"] = "em_cotacao"
                        if "cotacao_id" in df_pedidos.columns:
                            df_pedidos.at[idx, "cotacao_id"] = str(novo_id)
                    escrever_df("pedidos", df_pedidos)

                st.session_state["cotacao_criada"] = {"id": novo_id, "links": links, "nome": nome_cot}
                st.cache_data.clear()
                st.rerun()

    # Mostrar links após criação
    if "cotacao_criada" in st.session_state:
        info = st.session_state.pop("cotacao_criada")
        label_cot = info["nome"] if info.get("nome") else f"#{info['id']}"
        st.success(f"✅ Cotação **{label_cot}** criada! Envie os links abaixo para cada fornecedor:")
        for nome, link in info["links"].items():
            st.markdown(f"**{nome}**")
            st.code(link, language=None)


# ── Em Andamento ──────────────────────────────────────────────────────────────
with tab_abertas:
    cotacoes_abertas = (
        df_cotacoes[df_cotacoes["status"] == "aberta"]
        if not df_cotacoes.empty else pd.DataFrame()
    )

    if cotacoes_abertas.empty:
        st.info("Nenhuma cotação em andamento.")
    else:
        for _, cot in cotacoes_abertas.iterrows():
            cot_id = _safe_int(cot["id"])
            nome_cot_val = str(cot.get("nome", "") or "").strip()
            label_cot_aberta = nome_cot_val if nome_cot_val else f"#{cot_id}"
            prazo_dt     = _prazo_br(str(cot["prazo_limite"]))
            expirada     = _agora_br() > prazo_dt
            status_label = "⏰ Expirada" if expirada else "🟢 Aberta"

            with st.expander(
                f"{label_cot_aberta} — {status_label} — Prazo: {prazo_dt.strftime('%d/%m/%Y %H:%M')}"
            ):
                # Tokens desta cotação
                toks_cot = (
                    df_tokens[df_tokens["cotacao_id"].apply(_safe_int) == cot_id]
                    if not df_tokens.empty else pd.DataFrame()
                )

                # Respostas por fornecedor
                resps_cot = (
                    df_respostas[df_respostas["cotacao_id"].apply(_safe_int) == cot_id]
                    if not df_respostas.empty else pd.DataFrame()
                )
                forn_responderam = set(
                    resps_cot["fornecedor_id"].apply(_safe_int).tolist()
                ) if not resps_cot.empty else set()

                n_resp = len(forn_responderam)
                n_total = len(toks_cot)
                st.write(f"Respostas recebidas: **{n_resp}/{n_total}** fornecedores")

                # Status por fornecedor + link
                if not toks_cot.empty:
                    st.markdown("**Links e situação:**")
                    for _, tr in toks_cot.iterrows():
                        fid = _safe_int(tr["fornecedor_id"])
                        tok = str(tr["token"])
                        forn_row = (
                            df_fornecedores[df_fornecedores["id"].apply(_safe_int) == fid]
                            if not df_fornecedores.empty else pd.DataFrame()
                        )
                        nome_f = str(forn_row.iloc[0]["razao_social"]) if not forn_row.empty else f"Fornecedor {fid}"
                        respondeu = fid in forn_responderam
                        icone = "✅" if respondeu else "⏳"
                        link = f"{BASE_URL}/?token={tok}"
                        col_icon, col_link, col_btn = st.columns([3, 5, 2])
                        col_icon.markdown(f"{icone} **{nome_f}**")
                        col_link.code(link, language=None)
                        if respondeu:
                            if col_btn.button(
                                "🔓 Liberar", key=f"liberar_{cot_id}_{fid}",
                                help="Apaga a resposta atual e libera novo preenchimento",
                                use_container_width=True,
                            ):
                                df_respostas_upd = df_respostas[
                                    ~(
                                        (df_respostas["cotacao_id"].apply(_safe_int) == cot_id) &
                                        (df_respostas["fornecedor_id"].apply(_safe_int) == fid)
                                    )
                                ].reset_index(drop=True)
                                escrever_df("respostas", df_respostas_upd)
                                st.success(f"Resposta de {nome_f} apagada. O fornecedor pode preencher novamente.")
                                st.cache_data.clear()
                                st.rerun()

                st.markdown("---")

                # Alterar prazo
                with st.form(f"prazo_{cot_id}"):
                    st.markdown("**Alterar prazo:**")
                    c1, c2 = st.columns(2)
                    _prazo_local = prazo_dt.astimezone(ZoneInfo("America/Sao_Paulo"))
                    novo_prazo = c1.date_input(
                        "Nova data", value=_prazo_local.date(), key=f"nd_{cot_id}",
                        format="DD/MM/YYYY",
                    )
                    nova_hora = c2.time_input(
                        "Nova hora", value=_prazo_local.time(), key=f"nh_{cot_id}",
                        step=3600,
                    )
                    salvar_prazo = st.form_submit_button("Salvar prazo")

                if salvar_prazo:
                    novo_prazo_iso = datetime.datetime.combine(novo_prazo, nova_hora).isoformat()
                    idx = df_cotacoes[df_cotacoes["id"].apply(_safe_int) == cot_id].index[0]
                    df_cotacoes.at[idx, "prazo_limite"] = novo_prazo_iso
                    escrever_df("cotacoes", df_cotacoes)
                    st.success("Prazo atualizado.")
                    st.cache_data.clear()
                    st.rerun()

                # Encerrar — disponível sempre; aviso extra se ainda não venceu
                label_enc = "⛔ Encerrar cotação" if not expirada else "Encerrar e ir para análise"
                if not expirada:
                    st.caption("⚠️ O prazo ainda não venceu. Você pode encerrar antecipadamente se já tiver respostas suficientes.")
                if st.button(label_enc, key=f"enc_{cot_id}"):
                    idx = df_cotacoes[df_cotacoes["id"].apply(_safe_int) == cot_id].index[0]
                    df_cotacoes.at[idx, "status"] = "encerrada"
                    escrever_df("cotacoes", df_cotacoes)
                    st.success("Cotação encerrada. Acesse a aba Análise.")
                    st.cache_data.clear()
                    st.rerun()


# ── Encerradas ────────────────────────────────────────────────────────────────
with tab_encerradas:
    cotacoes_enc = (
        df_cotacoes[df_cotacoes["status"] == "encerrada"]
        if not df_cotacoes.empty else pd.DataFrame()
    )

    if cotacoes_enc.empty:
        st.info("Nenhuma cotação encerrada.")
    else:
        for _, cot in cotacoes_enc.sort_values("id", ascending=False).iterrows():
            cot_id = _safe_int(cot["id"])
            nome_cot_enc = str(cot.get("nome", "") or "").strip()
            label_cot_enc = nome_cot_enc if nome_cot_enc else f"#{cot_id}"
            try:
                prazo_dt  = _prazo_br(str(cot["prazo_limite"]))
                prazo_str = prazo_dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                prazo_str = "—"

            resps_cot = (
                df_respostas[df_respostas["cotacao_id"].apply(_safe_int) == cot_id]
                if not df_respostas.empty else pd.DataFrame()
            )
            n_resp = len(resps_cot["fornecedor_id"].unique()) if not resps_cot.empty else 0

            toks_cot = (
                df_tokens[df_tokens["cotacao_id"].apply(_safe_int) == cot_id]
                if not df_tokens.empty else pd.DataFrame()
            )
            n_total = len(toks_cot)

            with st.expander(f"{label_cot_enc} — Prazo: {prazo_str} — {n_resp}/{n_total} respostas"):
                st.write(f"Criada por: **{cot.get('criado_por', '—')}**")
                st.write(f"Respostas: **{n_resp}** de **{n_total}** fornecedores")
                btn_reabrir, btn_excluir = st.columns(2)
                with btn_reabrir:
                    if st.button("Reabrir cotação", key=f"reabrir_{cot_id}", use_container_width=True):
                        idx = df_cotacoes[df_cotacoes["id"].apply(_safe_int) == cot_id].index[0]
                        df_cotacoes.at[idx, "status"] = "aberta"
                        escrever_df("cotacoes", df_cotacoes)
                        st.success("Cotação reaberta.")
                        st.cache_data.clear()
                        st.rerun()
                with btn_excluir:
                    if usuario.get("perfil") == "admin":
                        _del_key = f"del_cot_{cot_id}"
                        if not st.session_state.get(_del_key):
                            if st.button("🗑️ Excluir", key=f"exc_{cot_id}", use_container_width=True):
                                st.session_state[_del_key] = True
                                st.rerun()
                        else:
                            st.warning("Isso apagará a cotação e todas as respostas. Confirma?")
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("✅ Confirmar exclusão", key=f"exc_ok_{cot_id}", use_container_width=True, type="primary"):
                                    df_tokens_upd = df_tokens[df_tokens["cotacao_id"].apply(_safe_int) != cot_id].reset_index(drop=True)
                                    df_resp_upd   = df_respostas[df_respostas["cotacao_id"].apply(_safe_int) != cot_id].reset_index(drop=True)
                                    df_cot_upd    = df_cotacoes[df_cotacoes["id"].apply(_safe_int) != cot_id].reset_index(drop=True)
                                    escrever_df("cotacao_tokens", df_tokens_upd)
                                    escrever_df("respostas", df_resp_upd)
                                    escrever_df("cotacoes", df_cot_upd)
                                    st.session_state.pop(_del_key, None)
                                    st.cache_data.clear()
                                    st.rerun()
                            with c2:
                                if st.button("Cancelar", key=f"exc_no_{cot_id}", use_container_width=True):
                                    st.session_state.pop(_del_key, None)
                                    st.rerun()
