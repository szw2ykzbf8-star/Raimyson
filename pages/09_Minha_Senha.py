import streamlit as st
from modules.auth import requer_login, validar_senha, alterar_senha, hash_senha
from modules.google_sheets import ler_df

usuario = requer_login()

st.title("🔐 Alterar Minha Senha")
st.markdown("---")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if "minha_senha_v" not in st.session_state:
        st.session_state["minha_senha_v"] = 0

    with st.form(f"minha_senha_{st.session_state['minha_senha_v']}"):
        atual = st.text_input("Senha atual", type="password")
        nova = st.text_input("Nova senha (6–72 caracteres)", type="password")
        confirma = st.text_input("Confirmar nova senha", type="password")

        if st.form_submit_button("Alterar Senha", use_container_width=True):
            df = ler_df("usuarios")
            linha = df[df["login"] == usuario["login"]]
            if linha.empty or linha.iloc[0]["senha_hash"] != hash_senha(atual):
                st.error("Senha atual incorreta.")
            else:
                erro = validar_senha(nova)
                if erro:
                    st.error(erro)
                elif nova != confirma:
                    st.error("As senhas não coincidem.")
                else:
                    try:
                        alterar_senha(usuario["login"], nova)
                        st.session_state["minha_senha_v"] += 1
                        st.success("Senha alterada com sucesso!")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
