import streamlit as st
from modules.auth import requer_perfil
from modules.google_sheets import ler_df, append_linha, atualizar_linha, escrever_df

requer_perfil(["admin"])

st.title("🏷️ Categorias de Produtos")

df = ler_df("categorias")


def _next_id(df):
    if df.empty or "id" not in df.columns:
        return 1
    try:
        return int(df["id"].apply(lambda v: int(float(v)) if str(v).strip() not in ("", "nan") else 0).max()) + 1
    except Exception:
        return 1


tab_lista, tab_nova = st.tabs(["Categorias", "Nova Categoria"])

with tab_lista:
    if df.empty:
        st.info("Nenhuma categoria cadastrada.")
    else:
        cats = df.sort_values("nome", key=lambda x: x.str.lower(), ignore_index=True)
        for _, row in cats.iterrows():
            with st.expander(row["nome"]):
                novo_nome = st.text_input("Nome", value=row["nome"], key=f"nome_{row['id']}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Salvar", key=f"salvar_{row['id']}", use_container_width=True):
                        nome_limpo = novo_nome.strip()
                        if not nome_limpo:
                            st.error("Nome não pode ser vazio.")
                        else:
                            atualizar_linha("categorias", row["id"], {"nome": nome_limpo})
                            st.success("Categoria atualizada!")
                            st.cache_data.clear()
                            st.rerun()
                with col2:
                    if st.button("🗑️ Excluir", key=f"del_{row['id']}", use_container_width=True):
                        df_novo = df[df["id"].astype(str) != str(row["id"])]
                        escrever_df("categorias", df_novo)
                        st.success(f"Categoria '{row['nome']}' excluída.")
                        st.cache_data.clear()
                        st.rerun()

with tab_nova:
    with st.form("nova_categoria"):
        nome = st.text_input("Nome da categoria *", placeholder="Ex: Laticínios")
        salvar = st.form_submit_button("✅ Cadastrar", use_container_width=True)

    if salvar:
        nome_limpo = nome.strip()
        if not nome_limpo:
            st.error("Nome é obrigatório.")
        else:
            nomes_existentes = df["nome"].str.strip().str.lower().tolist() if not df.empty else []
            if nome_limpo.lower() in nomes_existentes:
                st.error(f"Categoria '{nome_limpo}' já existe.")
            else:
                novo_id = _next_id(df)
                append_linha("categorias", [novo_id, nome_limpo])
                st.success(f"Categoria '{nome_limpo}' cadastrada!")
                st.cache_data.clear()
                st.rerun()
