import pandas as pd
import plotly.express as px
import streamlit as st
from utils import (
    get_user_defi_positions,
    process_defi_data,
    get_defi_llama_yields,
    summarize_portfolio,
    format_number,
    get_alternatives_for_token,
    generate_investment_analysis,
    get_openai_api_key
)

def show_portfolio():
    st.title("Resumen de Portafolio DeFi")

    st.sidebar.header("Ajustes para el Portafolio")

    wallet_address = st.sidebar.text_input("Wallet Address")
    
    if "analyze" not in st.session_state:
        st.session_state["analyze"] = False

    if st.sidebar.button("Analizar Portafolio"):
        st.session_state["analyze"] = True

    if st.session_state["analyze"] and wallet_address and merlin_api_key:
        # Obtener datos del usuario
        result = get_user_defi_positions(wallet_address, st.secrets["merlin_api_key"])
        if 'error' not in result:
            df = process_defi_data(result)

            if not df.empty:
                st.subheader("Tus Posiciones DeFi")
                df_display = df.copy()
                df_display["balance_usd"] = df_display["balance_usd"].apply(lambda x: f"${format_number(x)}")
                st.dataframe(df_display, use_container_width=True)

                # Graficar
                if df['balance_usd'].sum() > 0:
                    st.subheader("Distribución de Balance USD")
                    c1, c2 = st.columns(2)

                    with c1:
                        df_grouped = df.groupby(['token_symbol','common_name'])['balance_usd'].sum().reset_index()
                        fig = px.pie(
                            df_grouped,
                            values='balance_usd',
                            names=df_grouped.apply(lambda x: f"{x['token_symbol']} ({x['common_name']})", axis=1),
                            title='Por Token/Protocolo'
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    with c2:
                        df_grouped_mod = df.groupby('module')['balance_usd'].sum().reset_index()
                        fig2 = px.pie(
                            df_grouped_mod,
                            values='balance_usd',
                            names='module',
                            title='Por Módulo'
                        )
                        st.plotly_chart(fig2, use_container_width=True)

                    # Métricas básicas
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Total Balance USD", f"${format_number(df['balance_usd'].sum())}")
                    col_b.metric("Núm. de Protocolos", len(df['common_name'].unique()))
                    col_c.metric("Núm. de Posiciones", len(df))

                    # Consultar alternativas DeFi Llama
                    st.subheader("Alternativas de Inversión DeFi")
                    llama_data = get_defi_llama_yields()
                    st.session_state["portfolio_summary"] = summarize_portfolio(df)

                    if 'error' not in llama_data:
                        for idx, row in df.iterrows():
                            with st.expander(f"{row['token_symbol']} en {row['common_name']}"):
                                alternatives = get_alternatives_for_token(row['token_symbol'], llama_data)
                                if alternatives:
                                    df_alt = pd.DataFrame(alternatives)
                                    df_alt['apy'] = df_alt['apy'].apply(lambda x: f"{x:.2f}%")
                                    df_alt['tvlUsd'] = df_alt['tvlUsd'].apply(lambda x: f"${format_number(x)}")
                                    st.dataframe(df_alt, use_container_width=True)

                                    # Análisis GPT
                                    openai_key = get_openai_api_key()
                                    analysis = generate_investment_analysis(row, alternatives, openai_key)
                                    st.markdown(f"**Análisis breve:** {analysis}")
                                else:
                                    st.info("No se encontraron alternativas.")
                    else:
                        st.warning("No se pudo consultar DeFiLlama.")
                else:
                    st.warning("No se encontraron posiciones > \$5 en esta wallet.")
            else:
                st.warning("No se encontraron posiciones DeFi > \$5 en esta wallet.")
        else:
            st.error(result["error"])

def main():
    show_portfolio()

if __name__ == "__main__":
    main()
