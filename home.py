# Chat.py
import streamlit as st
from utils import init_chat_history, render_chat

def main():
    st.set_page_config(page_title="Mi Agente DeFi - Chat", layout="wide")
    st.title("Chat DeFi")

        # Inicializar session_state si no existe
    if 'combined_df' not in st.session_state:
        st.session_state['combined_df'] = None
    if 'portfolio_summary' not in st.session_state:
        st.session_state['portfolio_summary'] = None
    if 'messages' not in st.session_state:
        st.session_state['messages'] = []

    init_chat_history()
    render_chat()

if __name__ == "__main__":
    main()
