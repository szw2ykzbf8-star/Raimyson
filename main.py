import html as _html
import streamlit as st
from src import auth, sheets as sh, utils
from src.config import INATIVIDADE_PADRAO_MIN
from src import telegram_bot as tg

st.set_page_config(
    page_title="FinTrack",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Estilos globais ─────────────────────────────────────────────────────────

st.markdown("""
<style>
.metric-card {
    background: #1A1F2E;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    border: 1px solid #2D3748;
}
.metric-label { font-size: 0.85rem; color: #A0AEC0; margin-bottom: 4px; }
.metric-value { font-size: 1.6rem; font-weight: 700; }
.verde { color: #2ECC71; }
.vermelho { color: #E74C3C; }
.amarelo { color: #F39C12; }
.azul { color: #3498DB; }
.lock-screen {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; min-height: 60vh; gap: 16px;
}
</style>
""", unsafe_allow_html=True)


# ─── Setup inicial ────────────────────────────────────────────────────────────

def tela_setup():
    st.title("🏦 FinTrack — Configuração Inicial")
    st.info("Bem-vindo! Configure seus PINs de acesso para começar.")

    with st.form("setup_form"):
        st.subheader("🔑 PIN de Abertura")
        pin_a = st.text_input("Senha (4–72 caracteres)", type="password", max_chars=72, key="sa1")
        pin_a2 = st.text_input("Confirmar senha", type="password", max_chars=72, key="sa2")

        st.subheader("🔐 PIN de Exclusão")
        st.caption("Senha diferente da anterior, usada para confirmar exclusões.")
        pin_e = st.text_input("Senha (4–72 caracteres)", type="password", max_chars=72, key="se1")
        pin_e2 = st.text_input("Confirmar senha", type="password", max_chars=72, key="se2")

        submitted = st.form_submit_button("Salvar e Continuar", use_container_width=True)

    if submitted:
        erros = []
        if len(pin_a) < 4:
            erros.append("Senha de abertura deve ter pelo menos 4 caracteres.")
        elif len(pin_a) > 72:
            erros.append("Senha de abertura deve ter no máximo 72 caracteres.")
        if pin_a != pin_a2:
            erros.append("Senhas de abertura não conferem.")
        if len(pin_e) < 4:
            erros.append("Senha de exclusão deve ter pelo menos 4 caracteres.")
        elif len(pin_e) > 72:
            erros.append("Senha de exclusão deve ter no máximo 72 caracteres.")
        if pin_e != pin_e2:
            erros.append("Senhas de exclusão não conferem.")
        if pin_a == pin_e:
            erros.append("Senha de abertura e exclusão devem ser diferentes.")

        if erros:
            for e in erros:
                st.error(e)
        else:
            auth.configurar_pins(pin_a, pin_e)
            st.session_state["authenticated"] = True
            auth.update_activity()
            st.success("PINs configurados com sucesso!")
            st.rerun()


# ─── Tela de login ────────────────────────────────────────────────────────────

def tela_login():
    # Esconde sidebar e botão de expandir na tela de login
    st.markdown("""
    <style>
    [data-testid="stSidebar"]       { display: none !important; }
    [data-testid="collapsedControl"]{ display: none !important; }
    </style>
    """, unsafe_allow_html=True)

    estado   = auth.get_estado_bloqueio()
    bloqueado = estado in (auth.LOCK_ABERTURA, auth.LOCK_EXCLUSAO)

    # Espaço vertical para centralizar
    st.markdown("<br>" * 5, unsafe_allow_html=True)

    # Coluna central estreita
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown(
            "<h1 style='text-align:center; margin-bottom:4px'>🔒 FinTrack</h1>"
            "<p style='text-align:center; color:#A0AEC0; margin-top:0'>Controle Financeiro Pessoal</p>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        if not bloqueado:
            with st.form("login_form"):
                pin = st.text_input("Senha de Acesso", type="password",
                                    placeholder="Digite sua senha",
                                    label_visibility="collapsed")
                submitted = st.form_submit_button("Entrar", use_container_width=True)

            if submitted:
                ok, msg = auth.autenticar(pin)
                if ok:
                    st.rerun()
                elif msg == "bloqueado":
                    st.error("🔒 Senha bloqueada.")
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.error("🔒 Acesso bloqueado após tentativas incorretas.")

        # Desbloqueio via código Telegram
        if bloqueado:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔓 Solicitar código de desbloqueio", use_container_width=True):
                st.session_state["_confirmar_codigo"] = True
                st.rerun()

            if st.session_state.get("_confirmar_codigo", False):
                st.warning("Enviar código de desbloqueio via Telegram?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Sim, enviar", use_container_width=True):
                        codigo, err = auth.gerar_codigo()
                        if err:
                            st.error(err)
                        else:
                            enviado = tg.enviar_codigo_desbloqueio(codigo)
                            if enviado:
                                st.success("Código enviado!")
                            else:
                                st.error("Falha ao enviar. Verifique o Telegram.")
                            st.session_state["_aguardando_codigo"] = True
                        st.session_state["_confirmar_codigo"] = False
                        st.rerun()
                with c2:
                    if st.button("Cancelar", use_container_width=True):
                        st.session_state["_confirmar_codigo"] = False
                        st.rerun()

            if st.session_state.get("_aguardando_codigo", False):
                with st.form("codigo_form"):
                    codigo_input = st.text_input("Código de desbloqueio", max_chars=6)
                    ok_btn = st.form_submit_button("Verificar", use_container_width=True)
                if ok_btn:
                    ok, msg = auth.verificar_codigo(codigo_input)
                    if ok:
                        st.session_state["_aguardando_codigo"] = False
                        st.success("Desbloqueado! Faça login.")
                        st.rerun()
                    else:
                        st.error(msg)


# ─── Dashboard ────────────────────────────────────────────────────────────────

def dashboard():
    auth.require_auth()

    # Garantir coluna fixa_id nos gastos (necessária para auto-lançamento de fixas)
    sh.ensure_sheet("gastos", [
        "id", "id_grupo", "data_compra", "data_fatura", "mes_referencia",
        "parcela_num", "total_parcelas", "valor_parcela", "valor_total",
        "categoria", "forma_pagamento", "conta_cartao", "descricao", "criado_em",
        "viagem_id", "fixa_id",
    ])

    # Banner de viagem ativa
    try:
        _viagem_ativa = sh.get_viagem_ativa()
        if _viagem_ativa:
            _v_nome = _viagem_ativa.get("nome", "")
            _v_dest = _viagem_ativa.get("destino", "")
            _v_fim  = str(_viagem_ativa.get("data_fim", ""))
            st.info(
                f"✈️ **Modo Viagem ativo:** {_v_nome} — {_v_dest}  ·  "
                f"Término: {utils.fmt_data(_v_fim)}  |  Alertas de categoria suspensos."
            )
    except Exception:
        pass

    # Banner: contas fixas não lançadas para o mês atual
    try:
        _mes_fixas = utils.mes_atual()
        _df_fixas_ativas = sh.get_fixas()
        if not _df_fixas_ativas.empty:
            _gdf_fixas_check = sh.get_gastos(_mes_fixas)
            _fixas_lancadas = (
                not _gdf_fixas_check.empty
                and "fixa_id" in _gdf_fixas_check.columns
                and (_gdf_fixas_check["fixa_id"].astype(str) != "").any()
            )
            if not _fixas_lancadas:
                _col_fx, _col_btn_fx = st.columns([4, 1])
                with _col_fx:
                    st.warning(
                        f"📋 **{len(_df_fixas_ativas)} conta(s) fixa(s)** não foram lançadas em "
                        f"{utils.formatar_mes(_mes_fixas)}. Clique para gerar automaticamente."
                    )
                with _col_btn_fx:
                    if st.button("📋 Lançar Fixas", key="btn_auto_fixas", use_container_width=True):
                        _res = sh.auto_lancar_fixas(_mes_fixas)
                        sh.invalidate("gastos")
                        if _res["lancados"] > 0:
                            st.success(f"✅ {_res['lancados']} fixa(s) lançada(s)!")
                        else:
                            st.info("Todas as fixas já estavam lançadas.")
                        st.rerun()
    except Exception:
        pass

    # Seletor de mês
    col_nav1, col_nav2, col_nav3 = st.columns([1, 3, 1])
    with col_nav1:
        if st.button("◀", use_container_width=True):
            mes = st.session_state.get("mes_atual", utils.mes_atual())
            st.session_state["mes_atual"] = utils.mes_anterior(mes)
    with col_nav3:
        if st.button("▶", use_container_width=True):
            mes = st.session_state.get("mes_atual", utils.mes_atual())
            st.session_state["mes_atual"] = utils.proximo_mes(mes)

    mes = st.session_state.get("mes_atual", utils.mes_atual())
    with col_nav2:
        st.markdown(f"<h2 style='text-align:center'>{utils.formatar_mes(mes)}</h2>",
                    unsafe_allow_html=True)

    # Dados do mês
    entradas_df = sh.get_entradas(mes)
    gastos_df = sh.get_gastos(mes)

    total_entradas = entradas_df["valor"].astype(float).sum() if not entradas_df.empty else 0
    total_gastos = gastos_df["valor_parcela"].astype(float).sum() if not gastos_df.empty else 0
    resultado_mes = total_entradas - total_gastos

    # Saldo total acumulado em todas as contas
    contas_df = sh.get_contas()
    todas_entradas_full = sh.get_entradas()
    todos_gastos_full = sh.get_gastos()
    todas_transf = sh.get_transferencias()
    todos_invest  = sh.get_investimentos()
    todos_criptos = sh.get_criptos("ATIVO")
    todos_pgtos   = sh.get_pagamentos_contas()
    saldo_total = sum(
        utils.calcular_saldo_conta(row["nome"], todas_entradas_full, todos_gastos_full, todas_transf, contas_df, todos_invest, todos_pgtos, todos_criptos)
        for _, row in contas_df.iterrows()
    ) if not contas_df.empty else 0

    # Comprometido em cartão (meses futuros)
    mes_atual_str = utils.mes_atual()
    if not todos_gastos_full.empty:
        futuros = todos_gastos_full[
            (todos_gastos_full["forma_pagamento"] == "Crédito") &
            (todos_gastos_full["mes_referencia"] > mes_atual_str)
        ]
        comprometido_cartao = futuros["valor_parcela"].astype(float).sum()
    else:
        comprometido_cartao = 0

    # Meta de economia
    meta = float(sh.get_config("meta_economia", "0") or 0)

    # Tooltips de detalhamento
    if not entradas_df.empty:
        by_fonte = entradas_df.groupby("fonte")["valor"].apply(lambda x: x.astype(float).sum())
        tip_entradas = "Por fonte:\n" + "\n".join(
            f"• {f}: {utils.fmt_brl(v)}" for f, v in by_fonte.items()
        )
    else:
        tip_entradas = "Nenhuma entrada neste mês."

    if not gastos_df.empty:
        by_cat = gastos_df.groupby("categoria")["valor_parcela"].apply(lambda x: x.astype(float).sum())
        tip_gastos = "Por categoria:\n" + "\n".join(
            f"• {c}: {utils.fmt_brl(v)}" for c, v in by_cat.sort_values(ascending=False).items()
        )
    else:
        tip_gastos = "Nenhum gasto neste mês."

    if comprometido_cartao > 0 and not todos_gastos_full.empty:
        futuros_det = todos_gastos_full[
            (todos_gastos_full["forma_pagamento"] == "Crédito") &
            (todos_gastos_full["mes_referencia"] > mes_atual_str)
        ]
        by_mes = futuros_det.groupby("mes_referencia")["valor_parcela"].apply(lambda x: x.astype(float).sum())
        tip_comprometido = "Por mês:\n" + "\n".join(
            f"• {utils.formatar_mes(m)}: {utils.fmt_brl(v)}" for m, v in sorted(by_mes.items())
        )
    else:
        tip_comprometido = "Nenhum valor comprometido em cartão."

    if not contas_df.empty:
        saldos_por_conta = []
        for _, row in contas_df.iterrows():
            sc = utils.calcular_saldo_conta(row["nome"], todas_entradas_full, todos_gastos_full, todas_transf, contas_df, todos_invest, todos_pgtos, todos_criptos)
            saldos_por_conta.append(f"• {row['nome']} ({row['tipo']}): {utils.fmt_brl(sc)}")
        tip_saldo = "Por conta:\n" + "\n".join(saldos_por_conta)
    else:
        tip_saldo = "Nenhuma conta cadastrada."

    # Cards principais
    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("💰 Entradas do Mês", utils.fmt_brl(total_entradas), help=tip_entradas)
    with c2:
        st.metric("💸 Saídas do Mês", utils.fmt_brl(total_gastos), help=tip_gastos)
    with c3:
        st.metric("💳 Comprometido (Cartão)", utils.fmt_brl(comprometido_cartao), help=tip_comprometido)
    with c4:
        st.metric("🏦 Saldo Total em Contas", utils.fmt_brl(saldo_total), help=tip_saldo)

    st.markdown("")

    # Meta de economia
    if meta > 0:
        pct_meta = min(100, int((resultado_mes / meta) * 100)) if meta else 0
        st.markdown(f"**🎯 Meta de Economia: {utils.fmt_brl(meta)}**")
        st.progress(pct_meta / 100, text=f"{pct_meta}% atingido")
        st.markdown("")

    # Alertas de categoria
    alertas_raw = sh.get_config("alertas_categorias", "")
    if alertas_raw and not gastos_df.empty:
        import json
        try:
            alertas = json.loads(alertas_raw)
            for cat, limite in alertas.items():
                limite = float(limite)
                if limite <= 0:
                    continue
                gasto_cat = gastos_df[gastos_df["categoria"] == cat]["valor_parcela"].astype(float).sum()
                if gasto_cat >= limite * 0.8:
                    cor = "🚨" if gasto_cat >= limite else "⚠️"
                    pct = int((gasto_cat / limite) * 100)
                    st.warning(f"{cor} **{cat}**: {utils.fmt_brl(gasto_cat)} de {utils.fmt_brl(limite)} ({pct}%)")
        except Exception:
            pass

    # ── Alertas Inteligentes ──────────────────────────────────────────────────
    import calendar as _cal
    from datetime import date as _date, timedelta as _td

    _insights = []
    _hoje_d = _date.today()
    _dias_mes = _cal.monthrange(_hoje_d.year, _hoje_d.month)[1]
    _pct_mes = _hoje_d.day / _dias_mes * 100

    # Dados base para projeções melhoradas
    _df_fx_alrt = sh.get_fixas()
    _total_fixas_esp = (
        _df_fx_alrt["valor_referencia"].astype(float).sum()
        if not _df_fx_alrt.empty and "valor_referencia" in _df_fx_alrt.columns else 0.0
    )

    # Separar gastos variáveis (sem fixa_id) de fixos (com fixa_id)
    _has_fixa_col = not gastos_df.empty and "fixa_id" in gastos_df.columns
    if _has_fixa_col:
        _df_gvar = gastos_df[gastos_df["fixa_id"].astype(str) == ""]
        _df_gfix = gastos_df[gastos_df["fixa_id"].astype(str) != ""]
    else:
        _df_gvar = gastos_df
        _df_gfix = gastos_df.iloc[0:0] if not gastos_df.empty else gastos_df

    _val_gvar    = _df_gvar["valor_parcela"].astype(float).sum() if not _df_gvar.empty else 0.0
    _val_gfix    = _df_gfix["valor_parcela"].astype(float).sum() if not _df_gfix.empty else 0.0
    # Custo de fixas: usa o maior entre o já lançado e o esperado (conservador)
    _custo_fixas = max(_val_gfix, _total_fixas_esp)

    # Projeção melhorada: variáveis projetadas linearmente + fixas como valor único
    _proj_var_fim = (_val_gvar / _hoje_d.day * _dias_mes) if _hoje_d.day > 0 else _val_gvar
    _proj_tot_fim = _proj_var_fim + _custo_fixas

    # Cash flow: apenas gastos não-crédito (impacto imediato no caixa)
    if not gastos_df.empty:
        _df_gcash  = gastos_df[gastos_df["forma_pagamento"] != "Crédito"]
        _val_gcash = _df_gcash["valor_parcela"].astype(float).sum() if not _df_gcash.empty else 0.0
    else:
        _val_gcash = 0.0
    _proj_cash_fim = (_val_gcash / _hoje_d.day * _dias_mes) if _hoje_d.day > 0 else _val_gcash

    # 1. Velocidade de gastos vs % do mês (apenas após dia 8 — início do mês é ruidoso)
    if _hoje_d.day >= 8 and total_entradas > 0 and total_gastos > 0:
        _pct_gasto = total_gastos / total_entradas * 100
        if _pct_gasto > _pct_mes + 15:
            _insights.append(("⚡", "warning",
                f"**Ritmo acelerado:** {_pct_gasto:.0f}% da renda gasta com {_pct_mes:.0f}% do mês. "
                f"Projeção: **{utils.fmt_brl(_proj_tot_fim)}** "
                f"(variável {utils.fmt_brl(_proj_var_fim)} + fixas {utils.fmt_brl(_custo_fixas)})."))
        elif _pct_gasto < _pct_mes - 25 and _pct_mes > 50:
            _insights.append(("✅", "success",
                f"**Ritmo saudável:** só {_pct_gasto:.0f}% da renda gasta com {_pct_mes:.0f}% do mês."))

    # 2. Déficit de caixa projetado — apenas gastos à vista/débito/pix, após dia 8
    if _hoje_d.day >= 8 and _val_gcash > 0:
        _saldo_cash_proj = total_entradas - _proj_cash_fim
        if _saldo_cash_proj < 0:
            _insights.append(("🚨", "error",
                f"**Déficit de caixa projetado:** considerando gastos à vista/débito/pix, "
                f"você pode fechar o mês com **{utils.fmt_brl(abs(_saldo_cash_proj))}** negativo "
                f"(parcelas de crédito não estão incluídas nesta projeção)."))

    # 3. Conta com saldo negativo
    for _, _c_row in contas_df.iterrows():
        _sc = utils.calcular_saldo_conta(
            _c_row["nome"], todas_entradas_full, todos_gastos_full,
            todas_transf, contas_df, todos_invest, todos_pgtos, todos_criptos)
        if _sc < 0:
            _insights.append(("🔴", "error",
                f"**{_c_row['nome']}** está com saldo negativo: **{utils.fmt_brl(_sc)}**."))

    # 4. Contas fixas como % da renda (reutiliza _df_fx_alrt carregado acima)
    if total_entradas > 0 and _total_fixas_esp > 0:
        _pct_fixas = _total_fixas_esp / total_entradas * 100
        if _pct_fixas > 40:
            _insights.append(("⚠️", "warning",
                f"**Comprometimento alto:** suas fixas ({utils.fmt_brl(_total_fixas_esp)}) "
                f"representam **{_pct_fixas:.0f}%** da renda do mês (recomendado: < 30%)."))

    # 5. Investimentos vencendo em até 15 dias
    if not todos_invest.empty and "data_vencimento" in todos_invest.columns:
        _em_15 = (_date.today() + _td(days=15)).isoformat()
        _hoje_iso = _date.today().isoformat()
        _venc = todos_invest[
            (todos_invest["status"] == "ATIVO") &
            (todos_invest["data_vencimento"].astype(str) >= _hoje_iso) &
            (todos_invest["data_vencimento"].astype(str) <= _em_15)
        ]
        for _, _irow in _venc.iterrows():
            _insights.append(("📅", "warning",
                f"**Investimento vencendo:** **{_irow['nome']}** vence em "
                f"**{utils.fmt_data(str(_irow['data_vencimento']))}** "
                f"({utils.fmt_brl(float(_irow['valor_aplicado']))})."))

    # 6. Categoria acima de 130% da média dos últimos 3 meses
    if not gastos_df.empty:
        _meses_hist3 = [utils.mes_anterior(mes),
                        utils.mes_anterior(utils.mes_anterior(mes)),
                        utils.mes_anterior(utils.mes_anterior(utils.mes_anterior(mes)))]
        for _cat in gastos_df["categoria"].unique():
            _val_atual = gastos_df[gastos_df["categoria"] == _cat]["valor_parcela"].astype(float).sum()
            _vals_h = []
            for _mh in _meses_hist3:
                _dfh = sh.get_gastos(_mh)
                if not _dfh.empty:
                    _vh = _dfh[_dfh["categoria"] == _cat]["valor_parcela"].astype(float).sum()
                    if _vh > 0:
                        _vals_h.append(_vh)
            if _vals_h:
                _media_h = sum(_vals_h) / len(_vals_h)
                if _media_h > 0 and _val_atual > _media_h * 1.3:
                    _mult = _val_atual / _media_h
                    _insights.append(("📊", "warning",
                        f"**{_cat} acima da média:** {utils.fmt_brl(_val_atual)} "
                        f"({_mult:.1f}× a média de {utils.fmt_brl(_media_h)} dos últimos {len(_vals_h)} meses)."))

    # Exibir alertas
    if _insights:
        st.markdown("---")
        st.subheader("💡 Insights")
        for _icon, _level, _msg in _insights:
            getattr(st, _level)(f"{_icon} {_msg}")

    st.markdown("---")
    col_l, col_r = st.columns(2)

    # Últimas entradas
    with col_l:
        st.subheader("💰 Últimas Entradas")
        if not entradas_df.empty:
            df_show = entradas_df[["data", "fonte", "valor"]].copy()
            df_show["data"] = df_show["data"].apply(utils.fmt_data)
            df_show["valor"] = df_show["valor"].astype(float).apply(utils.fmt_brl)
            df_show.columns = ["Data", "Fonte", "Valor"]
            st.dataframe(df_show.tail(10), use_container_width=True, hide_index=True)
        else:
            st.caption("Nenhuma entrada neste mês.")

    # Últimos gastos
    with col_r:
        st.subheader("💸 Últimos Gastos")
        if not gastos_df.empty:
            df_show = gastos_df[["data_compra", "categoria", "forma_pagamento", "valor_parcela"]].copy()
            df_show["data_compra"] = df_show["data_compra"].apply(utils.fmt_data)
            df_show["valor_parcela"] = df_show["valor_parcela"].astype(float).apply(utils.fmt_brl)
            df_show.columns = ["Data", "Categoria", "Pagamento", "Valor"]
            st.dataframe(df_show.tail(10), use_container_width=True, hide_index=True)
        else:
            st.caption("Nenhum gasto neste mês.")

    # Saldos por conta
    st.markdown("---")
    st.subheader("🏦 Saldo por Conta")
    if not contas_df.empty:
        cols = st.columns(len(contas_df))
        for i, (_, row) in enumerate(contas_df.iterrows()):
            saldo_c = utils.calcular_saldo_conta(
                row["nome"], todas_entradas_full, todos_gastos_full,
                todas_transf, contas_df, todos_invest, todos_pgtos, todos_criptos
            )
            cor   = "verde" if saldo_c >= 0 else "vermelho"
            nome  = _html.escape(str(row["nome"]))
            tipo  = _html.escape(str(row["tipo"]))
            with cols[i]:
                st.markdown(f"""
                <div class='metric-card'>
                    <div class='metric-label'>{nome}</div>
                    <div class='metric-value {cor}'>{utils.fmt_brl(saldo_c)}</div>
                    <div class='metric-label'>{tipo}</div>
                </div>""", unsafe_allow_html=True)
    else:
        st.caption("Nenhuma conta cadastrada.")


# ─── Página principal (roteamento auth) ──────────────────────────────────────

def page_main():
    try:
        if auth.is_primeiro_acesso():
            tela_setup()
        elif not auth.is_authenticated():
            tela_login()
        else:
            st.title("🏠 Dashboard")
            dashboard()
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        st.info("Verifique as configurações no arquivo .env e se a planilha foi inicializada.")
        if st.button("Tentar novamente"):
            st.cache_resource.clear()
            st.rerun()


# ─── Navegação com seções ─────────────────────────────────────────────────────

pg = st.navigation(
    {
        "": [
            st.Page(page_main, title="Main", icon="🏠", default=True),
        ],
        "Movimentações": [
            st.Page("pages/02_Entradas.py",       title="Entradas",       icon="💰"),
            st.Page("pages/03_Gastos.py",          title="Gastos",         icon="💸"),
            st.Page("pages/04_Cartoes.py",         title="Cartões",        icon="💳"),
            st.Page("pages/05_Contas_a_Pagar.py",  title="Contas a Pagar", icon="📅"),
            st.Page("pages/06_Fixas.py",           title="Contas Fixas",   icon="📋"),
            st.Page("pages/07_Dividas.py",         title="Dívidas",        icon="🔴"),
            st.Page("pages/13_Viagens.py",         title="Viagens",        icon="✈️"),
        ],
        "Patrimônio": [
            st.Page("pages/08_Contas.py",          title="Contas Bancárias", icon="🏦"),
            st.Page("pages/09_Investimentos.py",   title="Investimentos",    icon="📈"),
            st.Page("pages/10_Criptos.py",         title="Criptomoedas",     icon="🪙"),
        ],
        "Análises": [
            st.Page("pages/11_Relatorios.py",      title="Relatórios",     icon="📊"),
        ],
        "Sistema": [
            st.Page("pages/12_Admin.py",           title="Administração",  icon="⚙️"),
        ],
    },
    position="sidebar",
)
pg.run()
