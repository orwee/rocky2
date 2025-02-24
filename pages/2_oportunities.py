import streamlit as st
import re
import requests
import pandas as pd
import plotly.express as px
import openai
from utils import (
    get_defi_llama_yields,
    format_number,
    get_alternatives_for_token,
    get_openai_api_key
)

def parse_timestamp(ts):
    try:
        # Intenta convertir timestamp si es numérico
        if isinstance(ts, (int, float)):
            return pd.to_datetime(ts, unit='s')
        # Si es string, parsea directamente
        return pd.to_datetime(ts)
    except:
        return None
        
def render_opportunities_chat():
    st.set_page_config(page_title="Oportunidades DeFi - Chat", layout="wide")
    st.title("Chat de Oportunidades DeFi")

    # Inicializar el historial de chat
    if "opp_chat_messages" not in st.session_state:
        st.session_state["opp_chat_messages"] = [
            {"role": "assistant", "content": (
                "¡Hola! Soy tu asesor DeFi. Pregunta, por ejemplo:\n"
                "• 'muestra alternativas para BTC/bitcoin'\n"
                "• 'show alternatives for ETH/ethereum'\n"
                "• 'filtra por chain: arbitrum y APY > 5%'\n"
                "• 'filter by TVL > 1000000 and token: USDC'\n"
                "• 'dime las mejores alternativas del token BTC en arbitrum con APY > 10%'\n"
                "Recuerda que siempre se muestran máximo 3 oportunidades y el gráfico de la primera."
            )}
        ]

    # Mostrar el historial de chat
    for msg in st.session_state["opp_chat_messages"]:
        st.chat_message(msg["role"]).write(msg["content"])

    # Capturar la entrada del usuario
    user_input = st.chat_input("Escribe tu consulta:")
    if user_input:
        st.session_state["opp_chat_messages"].append({"role": "user", "content": user_input})
        st.chat_message("user").write(user_input)

        openai_api_key = get_openai_api_key()
        if not openai_api_key:
            ai_response = "Por favor, agrega tu OpenAI API key para continuar."
        else:
            # Extraer filtros del mensaje
            chain_match = re.search(r"(?:chain|blockchain)\s*(?:[:=]\s*|\s+de\s+)(\w+)", user_input.lower())
            token_match = re.search(r"(?:token|moneda|crypto|cryptocurrency)\s*[:=]\s*(\w+)", user_input.lower(), re.IGNORECASE)
            apy_match = re.search(r"apy\s*[>]\s*(\d+(?:\.\d+)?)", user_input.lower())
            tvl_match = re.search(r"tvl\s*[>]\s*(\d+)", user_input.lower())

            # Establecer filtros
            chain_filter = chain_match.group(1).lower() if chain_match else None
            token_filter = token_match.group(1).upper() if token_match else None
            min_apy = float(apy_match.group(1)) if apy_match else 0
            min_tvl = float(tvl_match.group(1)) if tvl_match else 0

            # Obtener datos de DeFi Llama
            llama_data = get_defi_llama_yields()
            if "error" in llama_data:
                ai_response = "Error al obtener datos de DeFi Llama."
            else:
                alternatives = []
                for pool in llama_data.get("data", []):
                    # Aplicar todos los filtros
                    if (
                        (not chain_filter or chain_filter in pool.get("chain", "").lower()) and
                        (not token_filter or token_filter in pool.get("symbol", "").upper()) and
                        pool.get("apy", 0) >= min_apy and
                        pool.get("tvlUsd", 0) >= min_tvl
                    ):
                        alternatives.append({
                            "symbol": pool.get("symbol", ""),
                            "project": pool.get("project", ""),
                            "chain": pool.get("chain", ""),
                            "apy": pool.get("apy", 0),
                            "tvlUsd": pool.get("tvlUsd", 0),
                            "pool": pool.get("pool", "N/A")
                        })

                alternatives.sort(key=lambda x: x.get("apy", 0), reverse=True)
                alternatives = alternatives[:3]
                st.session_state["last_alternatives"] = alternatives

                if alternatives:
                    response_text = "He encontrado las siguientes oportunidades:\n\n"
                    for alt in alternatives:
                        response_text += (
                            f"• {alt['project']} en {alt['chain']}, token {alt['symbol']}, "
                            f"APY: {alt['apy']:.2f}% - TVL: ${format_number(alt['tvlUsd'])} "
                            f"(Pool ID: {alt['pool']})\n\n"
                        )

                    # Mostrar gráfico de la primera opción automáticamente
                    first_pool_id = alternatives[0]["pool"]
                    chart_url = f"https://yields.llama.fi/chart/{first_pool_id}"
                    try:
                        chart_response = requests.get(chart_url, headers={"accept": "*/*"})
                        if chart_response.status_code == 200:
                            chart_data = chart_response.json()
                            if chart_data.get("status") == "success" and chart_data.get("data"):
                                df_chart = pd.DataFrame(chart_data["data"])
                                # Convertir timestamp usando la función personalizada
                                df_chart["timestamp"] = df_chart["timestamp"].apply(parse_timestamp)
                                # Eliminar filas con timestamp nulo
                                df_chart = df_chart.dropna(subset=["timestamp"])
                        
                                if not df_chart.empty:
                                    fig = px.line(
                                        df_chart,
                                        x="timestamp",
                                        y="apy",
                                        title=f"Evolución del APY para {alternatives[0]['project']} - {alternatives[0]['symbol']}",
                                        labels={"timestamp": "Fecha", "apy": "APY (%)"}
                                    )
                                    # Configurar formato de fecha en el eje x
                                    fig.update_xaxes(
                                        tickformat="%Y-%m-%d",
                                        tickangle=45
                                    )
                                    # Mejorar el formato del eje y (APY)
                                    fig.update_yaxes(
                                        tickformat=".2f",
                                        title_text="APY (%)"
                                    )
                                    st.plotly_chart(fig, use_container_width=True)
                                    response_text += "\nArriba puedes ver el gráfico de la primera opción."
                                else:
                                    response_text += "\nNo hay suficientes datos para mostrar el gráfico."
                    except Exception as e:
                        response_text += f"\nError al cargar el gráfico: {e}"

                    ai_response = response_text
                else:
                    ai_response = "No se encontraron oportunidades que cumplan con los filtros especificados."

        st.session_state["opp_chat_messages"].append({"role": "assistant", "content": ai_response})
        st.chat_message("assistant").write(ai_response)

def main():
    render_opportunities_chat()

if __name__ == "__main__":
    main()
