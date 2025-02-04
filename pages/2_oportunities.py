# pages/2_oportunities.py
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from utils import get_defi_llama_yields, format_number

def show_opportunities():
    st.set_page_config(page_title="Oportunidades DeFi", layout="wide")
    st.title("Oportunidades DeFi")
    
    st.sidebar.header("Filtros de búsqueda")

    # Filtros generales: se puede introducir un texto que se busque en alguna de las variables
    texto_busqueda = st.sidebar.text_input("Buscar (cadena, proyecto o token)", "")

    # Filtros específicos
    chain_filter    = st.sidebar.text_input("Filtrar por cadena (ej. Ethereum)", "")
    project_filter  = st.sidebar.text_input("Filtrar por proyecto (ej. lido)", "")
    token_filter    = st.sidebar.text_input("Filtrar por token (ej. STETH)", "")
    min_apy         = st.sidebar.number_input("APY mínimo (%)", min_value=0.0, value=0.0, step=0.1)
    min_tvl         = st.sidebar.number_input("TVL mínimo (USD)", min_value=0.0, value=0.0, step=1000.0)

    if st.sidebar.button("Buscar Oportunidades"):
        
        # Se consulta la API de DeFi Llama para obtener todas las oportunidades.
        data = get_defi_llama_yields()
        if "error" in data:
            st.error("Error al obtener las oportunidades desde DeFi Llama")
            return
        opportunities = data.get("data", [])
        
        # Aplicar los filtros ingresados
        filtered = []
        for opp in opportunities:
            # Filtro de búsqueda general: revisar si el texto aparece en la cadena, proyecto o símbolo
            if texto_busqueda:
                if not (texto_busqueda.lower() in opp.get("chain", "").lower() or
                        texto_busqueda.lower() in opp.get("project", "").lower() or
                        texto_busqueda.lower() in opp.get("symbol", "").lower()):
                    continue
            # Filtro por cadena
            if chain_filter:
                if chain_filter.lower() not in opp.get("chain", "").lower():
                    continue
            # Filtro por proyecto
            if project_filter:
                if project_filter.lower() not in opp.get("project", "").lower():
                    continue
            # Filtro por token/símbolo
            if token_filter:
                if token_filter.lower() not in opp.get("symbol", "").lower():
                    continue
            # Filtro por APY mínimo
            if opp.get("apy", 0) < min_apy:
                continue
            # Filtro por TVL mínimo
            if opp.get("tvlUsd", 0) < min_tvl:
                continue

            filtered.append(opp)
        
        if not filtered:
            st.info("No se encontraron oportunidades con los filtros aplicados.")
            return

        # Ordenar las oportunidades filtradas por APY de forma descendente
        filtered.sort(key=lambda x: x.get("apy", 0), reverse=True)
        
        st.subheader(f"Resultados encontrados: {len(filtered)} oportunidades")
        # Mostrar resultados en una tabla
        df = pd.DataFrame(filtered)
        # Dar formato a las columnas numéricas
        df["tvlUsd"] = df["tvlUsd"].apply(lambda x: f"${format_number(x)}")
        df["apy"]    = df["apy"].apply(lambda x: f"{x:.2f}%")
        st.dataframe(df[["chain", "project", "symbol", "tvlUsd", "apy", "pool"]], use_container_width=True)
        
        # Permitir al usuario elegir una oportunidad para ver su gráfico de evolución (se usará el pool ID)
        opciones = {f"{opp.get('project','')} - {opp.get('symbol','')} (Pool: {opp.get('pool','')})": opp for opp in filtered}
        seleccion = st.selectbox("Selecciona una oportunidad para ver el gráfico", list(opciones.keys()))
        oportunidad_seleccionada = opciones[seleccion]

        if st.button("Ver Gráfico"):
            pool_id = oportunidad_seleccionada.get("pool")
            chart_url = f"https://yields.llama.fi/chart/{pool_id}"
            
            try:
                chart_response = requests.get(chart_url, headers={"accept": "*/*"})
                if chart_response.status_code != 200:
                    st.error("Error al obtener datos del gráfico desde DeFi Llama")
                    return

                chart_data = chart_response.json()
                if chart_data.get("status") != "success":
                    st.error("No se pudo cargar el gráfico")
                    return

                chart_df = pd.DataFrame(chart_data.get("data", []))
                if chart_df.empty:
                    st.info("No se encontraron datos históricos para el gráfico")
                    return

                chart_df["timestamp"] = pd.to_datetime(chart_df["timestamp"])
                # Ejemplo: graficar la evolución del APY
                fig = px.line(chart_df, x="timestamp", y="apy", 
                              title=f"Evolución del APY - {oportunidad_seleccionada.get('project')}",
                              labels={"timestamp": "Fecha", "apy": "APY (%)"})
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Error al procesar el gráfico: {e}")

def main():
    show_opportunities()

if __name__ == "__main__":
    main()
