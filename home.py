# Chat.py
import streamlit as st
from utils import init_chat_history, render_chat

def main():
    st.set_page_config(page_title="Mi Agente DeFi - Chat", layout="wide")
    st.title("Chat DeFi")
        
    init_chat_history()
    render_chat()

    if "combined_df" not in st.session_state:
        st.session_state["combined_df"] = None
    
    if "analyze" not in st.session_state:
        st.session_state["analyze"] = False

if __name__ == "__main__":
    main()
