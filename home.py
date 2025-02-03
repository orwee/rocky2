# Chat.py
import streamlit as st
from utils import init_chat_history, render_chat

def main():
    st.set_page_config(page_title="Mi Agente DeFi - Chat", layout="wide")
    st.title("Chat DeFi")

    init_chat_history()
    render_chat()

if __name__ == "__main__":
    main()
