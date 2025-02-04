import streamlit as st
import pandas as pd


def main():
    st.set_page_config(page_title="Mi Agente DeFi - Chat y Alternativas", layout="wide")
    st.title("Mi Agente DeFi - Chat y Alternativas")


    # Sección de Chat DeFi
    st.header("Chat DeFi")
    init_chat_history()
    render_chat()

    st.markdown("---")

    # Sección para explorar alternativas
    render_alternatives()

if __name__ == "__main__":
    main()
