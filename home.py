import streamlit as st
import pandas as pd
from utils import (
    init_chat_history,
    render_chat,
    format_number,
    get_defi_llama_yields,
    get_alternatives_for_token,
    generate_investment_analysis
)

def render_alternatives():
    st.header("Explorador de Alternativas DeFi")
    st.markdown("Filtra las alternativas disponibles y simula tus posibles ganancias.")

    # Filtros para las alternativas
    col1, col2, col3 = st.columns(3)
    with col1:
        token_filter = st.text_input("Filtrar por Token (ej.: ETH, BTC)", value="")
    with col2:
        blockchain_filter = st.text_input("Filtrar por Blockchain", value="")
    with col3:
        min_tvl = st.number_input("TVL mínimo (USD)", min_value=0.0, value=0.0, step=1000.0)

    investment_amount = st.number_input("Monto de Inversión (USD)", min_value=0.0, value=1000.0, step=100.0)

    if st.button("Buscar alternativas"):
        llama_data = get_defi_llama_yields()
        if "error" in llama_data:
            st.error("Error al obtener datos de DeFiLlama: " + llama_data["error"])
        else:
            alternativas = []
            for pool in llama_data.get("data", []):
                match_token = token_filter.lower() in pool.get("symbol", "").lower() if token_filter else True
                match_chain = blockchain_filter.lower() in pool.get("chain", "").lower() if blockchain_filter else True
                match_tvl = float(pool.get("tvlUsd", 0)) >= min_tvl if min_tvl else True
                if match_token and match_chain and match_tvl:
                    alternativas.append(pool)
            if alternativas:
                df_alt = pd.DataFrame(alternativas)
                # Calcular ganancia potencial anual: inversión * (APY/100)
                if "apy" in df_alt.columns:
                    df_alt["Ganancia Anual Estimada (USD)"] = investment_amount * (df_alt["apy"] / 100)
                # Formatear columnas de salida
                df_alt["apy"] = df_alt["apy"].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "N/A")
                df_alt["tvlUsd"] = df_alt["tvlUsd"].apply(lambda x: f"${format_number(x)}")
                st.dataframe(df_alt, use_container_width=True)
            else:
                st.info("No se encontraron alternativas con los filtros seleccionados.")

def main():
    st.set_page_config(page_title="Mi Agente DeFi - Chat y Alternativas", layout="wide")
    st.title("Mi Agente DeFi - Chat y Alternativas")

    # Inicializa las variables de sesión solo si aún no existen
    if "combined_df" not in st.session_state:
        st.session_state["combined_df"] = None
    if "portfolio_summary" not in st.session_state:
        st.session_state["portfolio_summary"] = None
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    # Sección de Chat DeFi
    st.header("Chat DeFi")
    init_chat_history()
    render_chat()

    st.markdown("---")

    # Sección para explorar alternativas
    render_alternatives()

if __name__ == "__main__":
    main()
