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
    todos_invest = sh.get_investimentos()
    saldo_total = sum(
        utils.calcular_saldo_conta(row["nome"], todas_entradas_full, todos_gastos_full, todas_transf, contas_df, todos_invest)
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
            sc = utils.calcular_saldo_conta(row["nome"], todas_entradas_full, todos_gastos_full, todas_transf, contas_df)
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
                todas_transf, contas_df, todos_invest
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


# ─── Roteamento principal ─────────────────────────────────────────────────────

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
