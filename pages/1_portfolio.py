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

    # Inicializar variables en session_state si aún no existen
    if "combined_df" not in st.session_state:
        st.session_state["combined_df"] = None
    if "analyze" not in st.session_state:
        st.session_state["analyze"] = False

    # Entradas para direcciones de wallet
    wallet_address_1 = st.sidebar.text_input("Wallet Address 1")
    wallet_address_2 = st.sidebar.text_input("Wallet Address 2 (opcional)")
    wallet_address_3 = st.sidebar.text_input("Wallet Address 3 (opcional)")

    # Botón para actualizar/análisis de portafolios
    if st.sidebar.button("Analizar Portafolios"):
        # Si el usuario quiere actualizar, se fuerza el análisis y se limpia el DataFrame almacenado
        st.session_state["analyze"] = True
        st.session_state["combined_df"] = None

    # Si ya existe información almacenada, se muestra directamente junto a los gráficos y métricas
    if st.session_state["combined_df"] is not None:
        st.info("Mostrando datos almacenados. Si deseas actualizar, haz clic en 'Analizar Portafolios'.")
        df_display = st.session_state["combined_df"].copy()
        df_display["balance_usd"] = df_display["balance_usd"].apply(lambda x: f"${format_number(x)}")
        st.dataframe(df_display, use_container_width=True)

        # Mostrar gráficos y métricas si hay balances
        if st.session_state["combined_df"]['balance_usd'].sum() > 0:
            st.subheader("Distribución de Balance USD")
            c1, c2 = st.columns(2)

            with c1:
                df_grouped = st.session_state["combined_df"].groupby(['token_symbol','common_name'])['balance_usd'].sum().reset_index()
                fig = px.pie(
                    df_grouped,
                    values='balance_usd',
                    names=df_grouped.apply(lambda x: f"{x['token_symbol']} ({x['common_name']})", axis=1),
                    title='Por Token/Protocolo'
                )
                st.plotly_chart(fig, use_container_width=True)

            with c2:
                df_grouped_mod = st.session_state["combined_df"].groupby('wallet')['balance_usd'].sum().reset_index()
                fig2 = px.pie(
                    df_grouped_mod,
                    values='balance_usd',
                    names='wallet',
                    title='Por Wallet'
                )
                st.plotly_chart(fig2, use_container_width=True)

            col_a, col_b, col_c = st.columns(3)
            total_balance = st.session_state["combined_df"]['balance_usd'].sum()
            col_a.metric("Total Balance USD", f"${format_number(total_balance)}")
            col_b.metric("Núm. de Protocolos", len(st.session_state["combined_df"]['common_name'].unique()))
            col_c.metric("Núm. de Posiciones", len(st.session_state["combined_df"]))

        # También se mantiene el resumen del portafolio guardado (si se realizó el análisis)
        if "portfolio_summary" in st.session_state:
            st.subheader("Resumen del Portafolio")
            st.text(st.session_state["portfolio_summary"])

        return  # Termina la función para evitar reanálisis

    # Si no hay datos almacenados y el usuario pulsó el botón, se realiza el análisis
    if st.session_state["analyze"]:
        wallet_dict = {
            f"Wallet #{i+1}": addr
            for i, addr in enumerate([wallet_address_1, wallet_address_2, wallet_address_3])
            if addr
        }

        if not wallet_dict:
            st.warning("Por favor, ingresa al menos una dirección de wallet.")
            return

        combined_df = pd.DataFrame()
        errors = []

        for wallet_label, addr in wallet_dict.items():
            result = get_user_defi_positions(addr, st.secrets["merlin_api_key"])
            if 'error' not in result:
                df_wallet = process_defi_data(result)
                df_wallet['wallet'] = wallet_label
                combined_df = pd.concat([combined_df, df_wallet], ignore_index=True)
            else:
                errors.append(f"Error con {wallet_label} ({addr}): {result['error']}")

        if errors:
            for err in errors:
                st.error(err)

        if combined_df.empty:
            st.warning("No se encontraron posiciones DeFi > $5 para las direcciones ingresadas.")
            return

        st.subheader("Tus Posiciones DeFi Combinadas")
        df_display = combined_df.copy()
        df_display["balance_usd"] = df_display["balance_usd"].apply(lambda x: f"${format_number(x)}")
        columns_order = ['wallet'] + [col for col in df_display.columns if col != 'wallet']
        df_display = df_display[columns_order]

        # Guardar el DataFrame en session_state para usos futuros
        st.session_state['combined_df'] = combined_df
        st.dataframe(df_display, use_container_width=True)

        if combined_df['balance_usd'].sum() > 0:
            st.subheader("Distribución de Balance USD")
            c1, c2 = st.columns(2)

            with c1:
                df_grouped = combined_df.groupby(['token_symbol','common_name'])['balance_usd'].sum().reset_index()
                fig = px.pie(
                    df_grouped,
                    values='balance_usd',
                    names=df_grouped.apply(lambda x: f"{x['token_symbol']} ({x['common_name']})", axis=1),
                    title='Por Token/Protocolo'
                )
                st.plotly_chart(fig, use_container_width=True)

            with c2:
                df_grouped_mod = combined_df.groupby('wallet')['balance_usd'].sum().reset_index()
                fig2 = px.pie(
                    df_grouped_mod,
                    values='balance_usd',
                    names='wallet',
                    title='Por Wallet'
                )
                st.plotly_chart(fig2, use_container_width=True)

            col_a, col_b, col_c = st.columns(3)
            total_balance = combined_df['balance_usd'].sum()
            col_a.metric("Total Balance USD", f"${format_number(total_balance)}")
            col_b.metric("Núm. de Protocolos", len(combined_df['common_name'].unique()))
            col_c.metric("Núm. de Posiciones", len(combined_df))

            st.subheader("Alternativas de Inversión DeFi")
            llama_data = get_defi_llama_yields()

            # Guardar también el resumen del portafolio
            st.session_state["portfolio_summary"] = summarize_portfolio(combined_df)

            if 'error' not in llama_data:
                for idx, row in combined_df.iterrows():
                    with st.expander(f"{row['token_symbol']} en {row['common_name']}"):
                        alternatives = get_alternatives_for_token(row['token_symbol'], llama_data)
                        if alternatives:
                            df_alt = pd.DataFrame(alternatives)
                            df_alt['apy'] = df_alt['apy'].apply(lambda x: f"{x:.2f}%")
                            df_alt['tvlUsd'] = df_alt['tvlUsd'].apply(lambda x: f"${format_number(x)}")
                            st.dataframe(df_alt, use_container_width=True)
                            openai_key = get_openai_api_key()
                            analysis = generate_investment_analysis(row, alternatives, openai_key)
                            st.markdown(f"**Análisis breve:** {analysis}")
                        else:
                            st.info("No se encontraron alternativas.")
            else:
                st.warning("No se pudo consultar DeFiLlama.")
        else:
            st.warning("No se encontraron posiciones > \$5 en las direcciones ingresadas.")

def main():
    show_portfolio()

if __name__ == "__main__":
    main()
