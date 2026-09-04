import streamlit as st
import pandas as pd
import datetime
from modules.auth import requer_perfil
from modules.google_sheets import ler_df, escrever_df, append_linha
from config import TIPOS_EMBALAGEM

st.set_page_config(page_title="Cotações", page_icon="💰", layout="wide")
usuario = requer_perfil(["admin", "comprador"])

st.title("💰 Cotações")

df_pedidos = ler_df("pedidos")
df_itens = ler_df("itens_pedido")
df_produtos = ler_df("produtos")
df_fornecedores = ler_df("fornecedores")
df_cotacoes = ler_df("cotacoes")
df_respostas = ler_df("respostas")

tab_nova, tab_abertas = st.tabs(["Nova Cotação", "Cotações em Andamento"])

with tab_nova:
    st.subheader("Consolidar pedidos e iniciar cotação")

    pedidos_bloqueados = df_pedidos[df_pedidos["status"] == "bloqueado"] if not df_pedidos.empty else pd.DataFrame()

    if pedidos_bloqueados.empty:
        st.info("Nenhum pedido bloqueado aguardando cotação.")
    else:
        st.write("Pedidos prontos para cotação:")
        for _, ped in pedidos_bloqueados.iterrows():
            itens = df_itens[df_itens["pedido_id"] == ped["id"]]
            st.write(f"• **#{ped['id']}** — {ped['unidade']} ({len(itens)} itens)")

        st.markdown("---")
        prazo = st.date_input("Data limite para resposta dos fornecedores", value=datetime.date.today() + datetime.timedelta(days=1))
        hora = st.time_input("Hora limite", value=datetime.time(12, 0))
        prazo_completo = datetime.datetime.combine(prazo, hora).isoformat()

        fornecedores_ativos = df_fornecedores[df_fornecedores["ativo"] == True] if not df_fornecedores.empty else pd.DataFrame()
        if not fornecedores_ativos.empty:
            selecionados = st.multiselect(
                "Fornecedores para esta cotação",
                options=fornecedores_ativos["id"].tolist(),
                format_func=lambda x: fornecedores_ativos[fornecedores_ativos["id"] == x]["razao_social"].values[0]
            )
        else:
            st.warning("Nenhum fornecedor ativo cadastrado.")
            selecionados = []

        if st.button("Iniciar Cotação", type="primary"):
            if not selecionados:
                st.error("Selecione ao menos um fornecedor.")
            else:
                novo_id = int(df_cotacoes["id"].max()) + 1 if not df_cotacoes.empty else 1
                append_linha("cotacoes", [
                    novo_id, datetime.datetime.now().isoformat(),
                    prazo_completo, "aberta", usuario["nome"]
                ])
                for _, ped in pedidos_bloqueados.iterrows():
                    idx = df_pedidos[df_pedidos["id"] == ped["id"]].index[0]
                    df_pedidos.at[idx, "status"] = "em_cotacao"
                escrever_df("pedidos", df_pedidos)
                st.success(f"Cotação #{novo_id} criada! Prazo: {prazo_completo}")
                st.info(f"Envie o link do formulário para os fornecedores selecionados.")
                st.cache_resource.clear()
                st.rerun()

with tab_abertas:
    if df_cotacoes.empty:
        st.info("Nenhuma cotação em andamento.")
    else:
        cotacoes_abertas = df_cotacoes[df_cotacoes["status"] == "aberta"]
        for _, cot in cotacoes_abertas.iterrows():
            prazo_dt = datetime.datetime.fromisoformat(str(cot["prazo_limite"]))
            expirada = datetime.datetime.now() > prazo_dt
            status_label = "⏰ Expirada" if expirada else "🟢 Aberta"
            with st.expander(f"Cotação #{cot['id']} — {status_label} — Prazo: {prazo_dt.strftime('%d/%m/%Y %H:%M')}"):
                respostas = df_respostas[df_respostas["cotacao_id"] == cot["id"]] if not df_respostas.empty else pd.DataFrame()
                st.write(f"Respostas recebidas: **{len(respostas['fornecedor_id'].unique()) if not respostas.empty else 0}** fornecedores")

                if expirada and cot["status"] == "aberta":
                    if st.button(f"Encerrar e ir para análise", key=f"encerrar_{cot['id']}"):
                        idx = df_cotacoes[df_cotacoes["id"] == cot["id"]].index[0]
                        df_cotacoes.at[idx, "status"] = "encerrada"
                        escrever_df("cotacoes", df_cotacoes)
                        st.success("Cotação encerrada. Acesse a aba Análise.")
                        st.cache_resource.clear()
                        st.rerun()
