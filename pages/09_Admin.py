import streamlit as st
import json
from src import auth, sheets as sh, utils
from src import telegram_bot as tg
from src.config import CATEGORIAS_PADRAO, FONTES_PADRAO, CFG_CHAVES_SENSIVEIS

st.set_page_config(page_title="Administração — FinTrack", page_icon="⚙️", layout="wide")
auth.require_auth()

# Admin exige verificação de ambos os PINs
if not st.session_state.get("admin_autenticado", False):
    st.title("⚙️ Administração")
    st.warning("🔐 Esta área requer verificação dupla de identidade.")
    with st.form("admin_auth"):
        pin_a = st.text_input("PIN de Abertura", type="password", max_chars=6)
        pin_e = st.text_input("PIN de Exclusão", type="password", max_chars=6)
        submitted = st.form_submit_button("Verificar", use_container_width=True)
    if submitted:
        hashed_a = sh.get_config(auth.PIN_ABERTURA, "")
        hashed_e = sh.get_config(auth.PIN_EXCLUSAO, "")
        if auth.verify_pin(pin_a, hashed_a) and auth.verify_pin(pin_e, hashed_e):
            st.session_state["admin_autenticado"] = True
            st.rerun()
        else:
            st.error("PINs incorretos.")
    st.stop()

st.title("⚙️ Administração")

tabs = st.tabs(["PINs", "Telegram", "Metas & Alertas", "Categorias", "Fontes", "Backup", "Config"])

# ─── PINs ────────────────────────────────────────────────────────────────────

with tabs[0]:
    st.subheader("🔑 Alterar PINs")

    with st.form("alter_pin_abertura"):
        st.markdown("**PIN de Abertura**")
        novo_a  = st.text_input("Novo PIN (6 dígitos)", type="password", max_chars=6, key="npa")
        novo_a2 = st.text_input("Confirmar", type="password", max_chars=6, key="npa2")
        btn_a   = st.form_submit_button("Alterar PIN de Abertura")
    if btn_a:
        if not novo_a.isdigit() or len(novo_a) != 6:
            st.error("PIN deve ter exatamente 6 dígitos numéricos.")
        elif novo_a != novo_a2:
            st.error("PINs não conferem.")
        else:
            sh.set_config(auth.PIN_ABERTURA, auth.hash_pin(novo_a))
            sh.set_config("tentativas_abertura", "0")
            st.success("PIN de abertura alterado!")

    st.markdown("---")

    with st.form("alter_pin_exclusao"):
        st.markdown("**PIN de Exclusão**")
        novo_e  = st.text_input("Novo PIN (6 dígitos)", type="password", max_chars=6, key="npe")
        novo_e2 = st.text_input("Confirmar", type="password", max_chars=6, key="npe2")
        btn_e   = st.form_submit_button("Alterar PIN de Exclusão")
    if btn_e:
        if not novo_e.isdigit() or len(novo_e) != 6:
            st.error("PIN deve ter exatamente 6 dígitos numéricos.")
        elif novo_e != novo_e2:
            st.error("PINs não conferem.")
        elif auth.verify_pin(novo_e, sh.get_config(auth.PIN_ABERTURA, "")):
            st.error("PIN de exclusão não pode ser igual ao de abertura.")
        else:
            sh.set_config(auth.PIN_EXCLUSAO, auth.hash_pin(novo_e))
            sh.set_config("tentativas_exclusao", "0")
            st.success("PIN de exclusão alterado!")

    st.markdown("---")
    st.subheader("🔒 Inatividade")
    timeout_atual = int(sh.get_config("inatividade_minutos", "30"))
    novo_timeout  = st.slider("Bloquear após (minutos)", 5, 120, timeout_atual)
    if st.button("Salvar timeout"):
        sh.set_config("inatividade_minutos", str(novo_timeout))
        st.success(f"Timeout definido para {novo_timeout} minutos.")

# ─── Telegram ────────────────────────────────────────────────────────────────

with tabs[1]:
    st.subheader("📱 Configuração do Telegram")
    st.info(
        "O Chat ID do Telegram é configurado exclusivamente via variável de ambiente "
        "`TELEGRAM_CHAT_ID` no arquivo `.env`. Reinicie o app após alterar o `.env`."
    )

    st.markdown("---")
    st.subheader("🧪 Testar Telegram")
    if st.button("Enviar mensagem de teste"):
        ok = tg.enviar_mensagem("✅ FinTrack — Teste de conexão bem-sucedido!")
        if ok:
            st.success("Mensagem enviada com sucesso!")
        else:
            st.error("Falha ao enviar. Verifique TELEGRAM_TOKEN e TELEGRAM_CHAT_ID no .env")

# ─── Metas & Alertas ─────────────────────────────────────────────────────────

with tabs[2]:
    st.subheader("🎯 Meta de Economia")
    meta_atual = float(sh.get_config("meta_economia", "0") or 0)
    nova_meta  = st.number_input("Meta mensal de economia (R$)", value=meta_atual,
                                  min_value=0.0, step=50.0, format="%.2f")
    if st.button("Salvar meta"):
        sh.set_config("meta_economia", str(nova_meta))
        st.success(f"Meta definida: {utils.fmt_brl(nova_meta)}")

    st.markdown("---")
    st.subheader("⚠️ Alertas por Categoria")
    st.caption("O sistema avisa quando atingir 80% do limite e quando ultrapassar.")

    cats_df = sh.get_categorias()
    alertas_raw = sh.get_config("alertas_categorias", "{}")
    try:
        alertas = json.loads(alertas_raw or "{}")
    except Exception:
        alertas = {}

    if not cats_df.empty:
        for _, row in cats_df.iterrows():
            cat          = row["nome"]
            limite_atual = float(alertas.get(cat, 0))
            novo_limite  = st.number_input(
                f"{cat}", value=limite_atual, min_value=0.0,
                step=50.0, format="%.2f",
                key=f"alerta_{cat}",
                help="0 = sem alerta"
            )
            alertas[cat] = novo_limite

        if st.button("Salvar alertas"):
            sh.set_config("alertas_categorias", json.dumps(alertas))
            st.success("Alertas salvos!")

# ─── Categorias ──────────────────────────────────────────────────────────────

with tabs[3]:
    st.subheader("📂 Categorias de Gasto")

    with st.form("nova_cat"):
        c1, c2 = st.columns([3, 1])
        with c1:
            nome_cat = st.text_input("Nome da categoria")
        with c2:
            icone_cat = st.text_input("Emoji", value="📦", max_chars=2)
        btn_cat = st.form_submit_button("Adicionar")
    if btn_cat and nome_cat:
        sh.add_categoria(nome_cat.strip(), icone_cat)
        st.success(f"Categoria '{nome_cat}' adicionada!")
        st.rerun()

    st.markdown("---")
    cats_df = sh.get_categorias()
    if not cats_df.empty:
        for _, row in cats_df.iterrows():
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"{row['icone']} {row['nome']}")
            with col2:
                if st.button("🗑️", key=f"del_cat_{row['id']}"):
                    sh.delete_categoria(row["id"])
                    sh.invalidate("categorias")
                    st.rerun()

# ─── Fontes ──────────────────────────────────────────────────────────────────

with tabs[4]:
    st.subheader("💰 Fontes de Renda")

    with st.form("nova_fonte"):
        nome_fonte = st.text_input("Nome da fonte (ex: Freelance)")
        btn_fonte  = st.form_submit_button("Adicionar")
    if btn_fonte and nome_fonte:
        sh.add_fonte(nome_fonte.strip())
        st.success(f"Fonte '{nome_fonte}' adicionada!")
        st.rerun()

    st.markdown("---")
    fontes_df = sh.get_fontes()
    if not fontes_df.empty:
        for _, row in fontes_df.iterrows():
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(row["nome"])
            with col2:
                if st.button("🗑️", key=f"del_fonte_{row['id']}"):
                    sh.delete_fonte(row["id"])
                    sh.invalidate("fontes")
                    st.rerun()

# ─── Backup ──────────────────────────────────────────────────────────────────

with tabs[5]:
    st.subheader("💾 Backup e Restauração")
    st.info("Os dados ficam salvos no Google Sheets. Use as opções abaixo como backup extra.")
    st.warning(
        "⚠️ O backup NÃO inclui hashes de PIN nem tokens de segurança. "
        "Configure esses itens manualmente após uma restauração."
    )

    if st.button("📥 Exportar todos os dados (JSON)"):
        backup = {}
        for key in ["categorias", "fontes", "contas", "cartoes",
                    "fixas", "dividas", "pgtos_divida", "investimentos",
                    "entradas", "gastos", "transferencias"]:
            df = sh.get_df(key, force=True)
            backup[key] = df.to_dict(orient="records") if not df.empty else []

        # Config: excluir chaves sensíveis
        df_cfg = sh.get_df("config", force=True)
        if not df_cfg.empty:
            backup["config"] = [
                r for _, r in df_cfg.iterrows()
                if r["chave"] not in CFG_CHAVES_SENSIVEIS
            ]
        else:
            backup["config"] = []

        backup_str = json.dumps(backup, ensure_ascii=False, indent=2)
        st.download_button(
            label="⬇️ Baixar backup.json",
            data=backup_str,
            file_name=f"fintrack_backup_{utils.mes_atual()}.json",
            mime="application/json",
        )

    st.markdown("---")
    st.subheader("📤 Importar backup")
    st.warning("⚠️ A importação NÃO sobrescreve dados existentes. Apenas adiciona registros novos (sem duplicatas por ID).")
    uploaded = st.file_uploader("Selecione o arquivo JSON", type=["json"])
    if uploaded and st.button("Importar"):
        st.info("Importação não implementada nesta versão — abra uma issue no repositório.")

# ─── Config geral ─────────────────────────────────────────────────────────────

with tabs[6]:
    st.subheader("🔧 Configurações Gerais")

    if st.button("🔄 Limpar cache (recarrega dados do Sheets)"):
        for key in list(st.session_state.keys()):
            if key.startswith("_sheet_cache_"):
                del st.session_state[key]
        st.success("Cache limpo!")

    st.markdown("---")
    if st.button("🚪 Sair da área administrativa"):
        st.session_state["admin_autenticado"] = False
        st.rerun()
